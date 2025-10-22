#!python
# -*- coding: utf-8 -*-
"""
Multi-timeframe candlestick pattern analyzer for XAUUSD (GC=F).
Detects common candlestick patterns on M15, H1, H4, D1 and forms a decision.

Author: professional AI+trader style implementation
Date: 2025-10-15
"""

import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime, timezone

# ---------- CONFIG ----------
SYMBOL = "GC=F"                      # COMEX Gold futures (proxy for XAUUSD)
TIMEFRAMES = {
    "M5": {"interval": "5m", "period": "1d"},   # shorter period ensures valid intraday data
    "M15":  {"interval": "15m", "period": "7d"},
    #"H4":  {"interval": "4h", "period": "60d"},
    #"D1":  {"interval": "1d", "period": "730d"}
}

OUTPUT_JSON = Path(r"f:\cap\candle_analysis_signal.json")

# Weights for timeframe importance (higher timeframe -> more weight)
TF_WEIGHTS = {"M15": 0.8, "H1": 1.0, "H4": 1.5, "D1": 2.0}

# Minimal constants
DOJI_PCT = 0.1  # body less than 10% of range => doji-like
HAMMER_BODY_MAX = 0.35  # small body relative to candle length
SHADOW_RATIO = 2.0      # long lower shadow (for hammer) at least 2x body
ENGULF_THRESHOLD = 1.0  # we require full engulf (abs sizes)

# ---------- Utilities ----------
def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def fetch_ohlc(symbol, interval, period):
    """Fetch OHLC data using yfinance. Returns DataFrame with columns: Open, High, Low, Close, Volume"""
    ticker = yf.Ticker(symbol)
    # yfinance sometimes requires exact interval formats; use given strings
    df = ticker.history(period=period, interval=interval, auto_adjust=False, back_adjust=False)
    if df.empty:
        return None
    df = df[['Open','High','Low','Close','Volume']].dropna()
    return df

# ---------- Candlestick pattern detectors ----------
def candle_components(row):
    o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
    body = abs(c - o)
    upper_shadow = h - max(c, o)
    lower_shadow = min(c, o) - l
    range_ = h - l if h > l else 1e-9
    return {"open":o, "high":h, "low":l, "close":c, "body":body,
            "upper":upper_shadow, "lower":lower_shadow, "range":range_}

def is_doji(row, pct=DOJI_PCT):
    comp = candle_components(row)
    return (comp["body"] <= pct * comp["range"])

def is_bullish_engulfing(prev_row, row):
    # current is bullish (close>open), previous is bearish (close<open)
    if prev_row is None: return False
    if not (prev_row['Close'] < prev_row['Open'] and row['Close'] > row['Open']):
        return False
    # current body engulfs previous body
    prev_low = min(prev_row['Open'], prev_row['Close'])
    prev_high = max(prev_row['Open'], prev_row['Close'])
    cur_low = min(row['Open'], row['Close'])
    cur_high = max(row['Open'], row['Close'])
    return (cur_low <= prev_low and cur_high >= prev_high)

def is_bearish_engulfing(prev_row, row):
    if prev_row is None: return False
    if not (prev_row['Close'] > prev_row['Open'] and row['Close'] < row['Open']):
        return False
    prev_low = min(prev_row['Open'], prev_row['Close'])
    prev_high = max(prev_row['Open'], prev_row['Close'])
    cur_low = min(row['Open'], row['Close'])
    cur_high = max(row['Open'], row['Close'])
    return (cur_low <= prev_low and cur_high >= prev_high)

def is_hammer(row):
    comp = candle_components(row)
    # small body near top, long lower shadow
    # body small relative to range and lower shadow >= SHADOW_RATIO * body
    if comp["body"] == 0:
        return False
    body_to_range = comp["body"] / comp["range"]
    return (body_to_range <= HAMMER_BODY_MAX) and (comp["lower"] >= SHADOW_RATIO * comp["body"]) and (comp["upper"] <= comp["body"] * 1.0)

def is_shooting_star(row):
    comp = candle_components(row)
    # small body near bottom, long upper shadow
    if comp["body"] == 0:
        return False
    body_to_range = comp["body"] / comp["range"]
    return (body_to_range <= HAMMER_BODY_MAX) and (comp["upper"] >= SHADOW_RATIO * comp["body"]) and (comp["lower"] <= comp["body"] * 1.0)

def is_morning_star(prev2, prev1, cur):
    # heuristic: prev2 bearish large, prev1 small body (doji/small), cur bullish closing well into prev2 body
    if prev2 is None or prev1 is None: return False
    if not (prev2['Close'] < prev2['Open']): return False
    if not is_doji(prev1): return False
    if not (cur['Close'] > cur['Open']): return False
    # cur close > midpoint of prev2
    prev2_mid = (prev2['Open'] + prev2['Close'])/2
    return cur['Close'] > prev2_mid

def is_evening_star(prev2, prev1, cur):
    if prev2 is None or prev1 is None: return False
    if not (prev2['Close'] > prev2['Open']): return False
    if not is_doji(prev1): return False
    if not (cur['Close'] < cur['Open']): return False
    prev2_mid = (prev2['Open'] + prev2['Close'])/2
    return cur['Close'] < prev2_mid

# ---------- Per-timeframe analysis ----------
def analyze_timeframe(df):
    """
    df must be indexed by datetime ascending
    returns dict: { 'patterns': [list], 'signal': 'BUY/SELL/HOLD', 'strength': float }
    patterns list contains tuples (pattern_name, index_timestamp)
    """
    patterns = []
    signal_score = 0.0  # positive -> bullish, negative -> bearish

    # operate on last 20 candles for context but detect on last candle primarily
    if df is None or df.empty:
        return {"patterns": patterns, "signal": "HOLD", "score": 0.0, "explain": "no data"}

    df = df.copy().tail(50)  # keep last 50 for pattern context
    df = df.reset_index()

    # Use last candle as 'cur'
    last_idx = len(df)-1
    cur = df.loc[last_idx]
    prev = df.loc[last_idx-1] if last_idx-1 >= 0 else None
    prev2 = df.loc[last_idx-2] if last_idx-2 >= 0 else None

    # detect patterns on the last candle (or last 3 for stars)
    if is_doji(cur):
        patterns.append(("Doji", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        # doji is neutral but may signal reversal if prior trend present
        # small adjustment: slight bullish/bearish based on previous candle direction
        if prev is not None:
            if prev['Close'] < prev['Open']:
                signal_score += 2  # possible bullish reversal
            else:
                signal_score -= 2

    if is_hammer(cur):
        patterns.append(("Hammer", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        signal_score += 20

    if is_shooting_star(cur):
        patterns.append(("Shooting Star", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        signal_score -= 20

    if is_bullish_engulfing(prev, cur):
        patterns.append(("Bullish Engulfing", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        signal_score += 30

    if is_bearish_engulfing(prev, cur):
        patterns.append(("Bearish Engulfing", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        signal_score -= 30

    if is_morning_star(prev2, prev, cur):
        patterns.append(("Morning Star", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        signal_score += 35

    if is_evening_star(prev2, prev, cur):
        patterns.append(("Evening Star", cur['Date'] if 'Date' in cur else df.index[last_idx]))
        signal_score -= 35

    # Also check previous candle for engulfing because some signals form across last-two candles
    # (already covered by is_bullish_engulfing/is_bearish_engulfing)

    # Normalize score to a simple signal
    if signal_score >= 25:
        sig = "BUY"
    elif signal_score <= -25:
        sig = "SELL"
    else:
        sig = "HOLD"

    explain = f"score={signal_score}"
    return {"patterns": patterns, "signal": sig, "score": float(signal_score), "explain": explain,
            "last_close": float(cur['Close']), "last_open": float(cur['Open'])}

# ---------- Aggregate multi-timeframe decision ----------
def aggregate_signals(tf_results, weights=TF_WEIGHTS):
    """
    Combine signals from multiple timeframes into a final decision.
    Each timeframe contributes signed score: BUY=+1, SELL=-1, HOLD=0 scaled by detected score and weight.
    Return final {'signal','confidence','details'}
    """
    total = 0.0
    weight_sum = 0.0
    details = {}

    for tf, res in tf_results.items():
        w = weights.get(tf, 1.0)
        weight_sum += w
        # map res['signal'] to base polarity
        polarity = 0
        if res['signal'] == "BUY":
            polarity = 1
        elif res['signal'] == "SELL":
            polarity = -1
        # scale by magnitude of res['score'] (if zero treat small)
        magnitude = abs(res.get('score', 0.0))
        # clamp magnitude to a reasonable range
        mag_norm = min(100.0, magnitude) / 100.0  # 0..1
        contribution = polarity * mag_norm * w
        total += contribution
        details[tf] = {"pattern_signal": res['signal'], "score": res.get('score',0.0), "contribution": contribution, "patterns": res['patterns']}

    # final polarity
    if weight_sum == 0:
        return {"signal": "HOLD", "confidence": 10, "details": details}

    avg = total / weight_sum  # -1..+1 roughly
    # Map avg to final signal and confidence
    if avg >= 0.25:
        final_signal = "BUY"
    elif avg <= -0.25:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"

    # confidence: scale |avg| into 0..100
    confidence = int(min(95, max(10, (abs(avg) * 100) + 10)))

    return {"signal": final_signal, "confidence": confidence, "avg": avg, "details": details}

# ---------- Main runner ----------
def run_candlestick_analysis(symbol=SYMBOL, timeframes=TIMEFRAMES):
    results = {}
    for tf, cfg in timeframes.items():
        print(f"Fetching {tf} -> interval {cfg['interval']} period {cfg['period']} ...")
        try:
            df = fetch_ohlc(symbol, cfg['interval'], cfg['period'])
        except Exception as e:
            print(f"Error fetching {tf}: {e}")
            df = None

        res = analyze_timeframe(df)
        results[tf] = res
        print(f"  {tf}: signal={res['signal']} score={res.get('score',0)} patterns={[p[0] for p in res['patterns']]}\n")

    agg = aggregate_signals(results)
    output = {
        "timestamp": now_iso(),
        "symbol": symbol,
        "timeframe_results": results,
        "final": agg
    }

    # Save JSON (safe write)
    try:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved analysis to {OUTPUT_JSON}")
    except Exception as e:
        print(f"Failed to save JSON: {e}")

    # print summary
    print("\n=== FINAL DECISION ===")
    print(f"Symbol: {symbol}")
    print(f"Signal: {agg['signal']}   Confidence: {agg['confidence']}%")
    print("Details per timeframe:")
    for tf, d in agg['details'].items():
        print(f" - {tf}: {d['pattern_signal']} | score={d['score']} | contrib={d['contribution']:.3f} patterns={[p[0] for p in d['patterns']]}")
    print("======================\n")

    LATEST_SIGNAL_FILE = Path(r"f:\cap\latest_signal.json")

    # Create dynamic new signal data
    new_signal = {
        "candle_Signal": agg['signal'],
        "candle_Confidence": f"{agg['confidence']}%"
    }

    # Load existing file if present
    if LATEST_SIGNAL_FILE.exists():
        try:
            with open(LATEST_SIGNAL_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"⚠️ Could not read existing {LATEST_SIGNAL_FILE}: {e}")
            existing_data = {}
    else:
        existing_data = {}

    # Update or add the new signal
    existing_data.update(new_signal)

    # Save back to JSON
    try:
        with open(LATEST_SIGNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Latest signal updated in {LATEST_SIGNAL_FILE}")
    except Exception as e:
        print(f"⚠️ Failed to save latest signal JSON: {e}")

    # ---------- Entrypoint ----------

    return output

# ---------- If run as script ----------
if __name__ == "__main__":
    out = run_candlestick_analysis()
