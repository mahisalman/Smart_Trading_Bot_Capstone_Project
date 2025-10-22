#!python

"""
XAUUSD Research -> Review -> Write pipeline
Fetches live prices from multiple sources, scrapes recent news, computes technical indicators,
constructs a simple rule-based prediction (BUY/HOLD/SELL) with confidence, and writes JSON output.

Author: (you)
Date: 2025-10-14 (example)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
import sqlite3


# ---------- CONFIG ----------
OUTPUT_JSON = Path(r"f:\cap\latest_xauusd_signal.json")  # change as needed
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

# Sources to query (scrape)
TRADINGVIEW_XAUUSD = "https://www.tradingview.com/symbols/XAUUSD/"     # interactive chart page
KITCO_GOLD = "https://www.kitco.com/price/precious-metals"            # kitco list page
REUTERS_GOLD_NEWS = "https://www.reuters.com/markets/commodities/"   # search news by scraping
YAHOO_FUTURES_SYMBOL = "GC=F"  # COMEX Gold Futures on Yahoo Finance (proxy for spot)



# Technical parameters
RSI_PERIOD = 14
SMA_SHORT = 20
SMA_LONG = 50
ATR_PERIOD = 14

# ---------- Utilities ----------
def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def safe_get(url, **kwargs):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"⚠️ Request error for {url}: {e}")
        return None

# ---------- Price fetchers ----------
def fetch_price_yahoo_futures():
    """Fetch last price from Yahoo Finance via yfinance (COMEX futures as proxy)."""
    try:
        ticker = yf.Ticker(YAHOO_FUTURES_SYMBOL)
        data = ticker.history(period="5d", interval="15m")  # small history for indicators
        if data.empty:
            return None
        data = data[['Close']].rename(columns={'Close': 'price'}).dropna()
        latest = float(data['price'].iloc[-1])
        return {"source": "yahoo_futures", "price": latest, "df": data}
    except Exception as e:
        print(f"⚠️ Yahoo fetch failed: {e}")
        return None

def fetch_price_tradingview_snapshot():
    """Attempt to get a price from TradingView page HTML (best-effort)."""
    r = safe_get(TRADINGVIEW_XAUUSD)
    if not r:
        return None
    html = r.text
    # Try to find a numeric price in the page text (best-effort)
    # TradingView loads data via JS; static scrape may find price snippets.
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    # Find patterns like 4,179.48 or 4179.48 (large numbers for 2025 scenario)
    import re
    m = re.search(r"([0-9]{1,3}(?:[,][0-9]{3})*(?:\.[0-9]{1,4})?)", text)
    if m:
        price_str = m.group(1).replace(",", "")
        try:
            price = float(price_str)
            return {"source": "tradingview_html", "price": price}
        except:
            return None
    return None

def fetch_price_kitco():
    """Try to parse a Kitco page for a spot/gold price (best-effort)."""
    r = safe_get(KITCO_GOLD)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    # Kitco often lists price with class or in a table; try common patterns
    # This is heuristic: find occurrences of 'Spot Gold' near a numeric text
    text = soup.get_text(separator=" | ", strip=True)
    import re
    matches = re.findall(r"Spot Gold[^\d]*([0-9]{1,3}(?:[,][0-9]{3})*(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if matches:
        price = float(matches[0].replace(",", ""))
        return {"source": "kitco", "price": price}
    # fallback: search any obvious numeric cluster
    m = re.search(r"([0-9]{1,3}(?:[,][0-9]{3})*(?:\.[0-9]{1,4})?)", text)
    if m:
        try:
            return {"source": "kitco_fallback", "price": float(m.group(1).replace(",", ""))}
        except:
            return None
    return None

def aggregate_price_samples(samples):
    """Aggregate multiple price samples into a single price and record sources."""
    valid = [s for s in samples if s and "price" in s]
    if not valid:
        return None
    prices = [v["price"] for v in valid]
    mean_px = float(np.mean(prices))
    median_px = float(np.median(prices))
    sources = [v["source"] for v in valid]
    return {"mean": mean_px, "median": median_px, "samples": valid, "sources": sources}

# ---------- News fetch & sentiment (simple) ----------
def fetch_reuters_gold_headlines(limit=6):
    """Pull recent lines from Reuters commodities page and filter for gold headlines."""
    r = safe_get(REUTERS_GOLD_NEWS)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    headlines = []
    # heuristics: find anchor text that mention 'gold'
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        if text and "gold" in text.lower():
            link = a['href']
            if link.startswith("/"):
                link = "https://www.reuters.com" + link
            headlines.append({"title": text, "link": link})
            if len(headlines) >= limit:
                break
    return headlines

def simple_sentiment_from_headlines(headlines):
    """Simple keyword-based sentiment score: positive -> +1, negative -> -1."""
    positive_keywords = ["gain", "rise", "rally", "surge", "up", "record", "bull"]
    negative_keywords = ["drop", "falls", "selloff", "down", "weak", "concern", "dip", "volatility", "correction"]
    score = 0
    for h in headlines:
        t = h['title'].lower()
        for pk in positive_keywords:
            if pk in t:
                score += 1
        for nk in negative_keywords:
            if nk in t:
                score -= 1
    # normalize to -1..+1
    if not headlines:
        return 0.0
    max_possible = len(headlines) * max(len(positive_keywords), len(negative_keywords))
    return float(score) / max(1, len(headlines))

# ---------- Technical indicators ----------
def compute_indicators_from_df(df_close):
    """Given a pandas Series or DataFrame['price'], compute indicators and return dict."""
    price = df_close.copy()
    if isinstance(price, pd.DataFrame):
        price = price['price']
    price = price.astype(float).dropna()
    indicators = {}
    if len(price) < max(SMA_LONG, RSI_PERIOD) + 2:
        # Not enough data to compute all indicators
        indicators['error'] = "Not enough history"
        indicators['latest_price'] = float(price.iloc[-1]) if len(price) else None
        return indicators

    # SMA
    indicators['sma_short'] = float(price.rolling(SMA_SHORT).mean().iloc[-1])
    indicators['sma_long'] = float(price.rolling(SMA_LONG).mean().iloc[-1])
    # EMA
    indicators['ema_20'] = float(price.ewm(span=20, adjust=False).mean().iloc[-1])
    # RSI
    delta = price.diff()
    gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    rs = gain / (loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    indicators['rsi_14'] = float(rsi.iloc[-1])
    # ATR-like (using close range, since no high/low here) use simple average true range proxy via abs(diff)
    indicators['atr_proxy'] = float(price.diff().abs().rolling(ATR_PERIOD).mean().iloc[-1])
    # Momentum
    indicators['momentum_5'] = float(price.pct_change(5).iloc[-1])
    # latest price
    indicators['latest_price'] = float(price.iloc[-1])
    return indicators

# ---------- Decision / signal logic ----------
def decide_signal(indicators, news_sentiment):
    """
    Very simple rules:
      - If price > SMA_long and momentum positive and news_sentiment >= 0 -> BUY
      - If price < SMA_long and momentum negative and news_sentiment <= 0 -> SELL
      - If RSI > 70 -> SELL (overbought); if RSI < 30 -> BUY (oversold)
      - Otherwise HOLD
    Confidence: composite score (0..100) based on indicator agreement and sentiment magnitude.
    """
    if not indicators or 'error' in indicators:
        return {"signal": "HOLD", "confidence": 20, "reasons": ["insufficient data"]}

    p = indicators['latest_price']
    sma_long = indicators.get('sma_long', p)
    momentum = indicators.get('momentum_5', 0)
    rsi = indicators.get('rsi_14', 50)

    score = 0
    reasons = []

    # Trend rule
    if p > sma_long and momentum > 0:
        score += 30
        reasons.append("price above long SMA and positive momentum")
    elif p < sma_long and momentum < 0:
        score -= 30
        reasons.append("price below long SMA and negative momentum")

    # RSI influence
    if rsi > 70:
        score -= 25
        reasons.append("RSI overbought")
    elif rsi < 30:
        score += 25
        reasons.append("RSI oversold")

    # News sentiment influence (range normalized roughly to +/-20)
    score += float(news_sentiment) * 20
    if news_sentiment > 0.1:
        reasons.append("positive news momentum")
    elif news_sentiment < -0.1:
        reasons.append("negative news momentum")

    # Map score to signal
    if score >= 20:
        signal = "BUY"
    elif score <= -20:
        signal = "SELL"
    else:
        signal = "HOLD"

    # Confidence scale 0..100: based on absolute score and number of reasons
    conf = min(95, max(10, int(50 + score)))  # baseline 50, shift by score
    return {"signal": signal, "confidence": conf, "score": score, "reasons": reasons}

# ---------- Main pipeline ----------
def run_pipeline():
    ts = now_iso()
    result = {
        "timestamp": ts,
        "sources_used": [],
        "price_samples": [],
        "price_aggregate": None,
        "technical_indicators": None,
        "news_headlines": [],
        "news_sentiment": None,
        "prediction": None,
        "notes": []
    }

    # 1) get price samples
    samples = []
    y = fetch_price_yahoo_futures()
    if y:
        samples.append({"source": y["source"], "price": float(y["df"]['price'].iloc[-1]) if "df" in y else float(y["price"])})
        # keep df for indicators (prefer futures history)
        df_for_indicators = y.get("df")
    else:
        df_for_indicators = None
    tv = fetch_price_tradingview_snapshot()
    if tv:
        samples.append(tv)
    k = fetch_price_kitco()
    if k:
        samples.append(k)

    # fallback: if no samples at all, abort gracefully
    if not samples:
        result["notes"].append("No price samples available from sources.")
        result["prediction"] = {"signal": "HOLD", "confidence": 10}
        print("❌ No price samples could be gathered. Exiting with HOLD.")
    else:
        result["price_samples"] = samples
        agg = aggregate_price_samples(samples)
        result["price_aggregate"] = {"mean": agg["mean"], "median": agg["median"], "sources": agg["sources"]}
        result["sources_used"] = agg["sources"]

        # 2) compute indicators - if we have a dataframe from yahoo we use that; else create a small df from sample prices (limited)
        if df_for_indicators is not None and isinstance(df_for_indicators, pd.DataFrame) and not df_for_indicators.empty:
            indicators = compute_indicators_from_df(df_for_indicators)
        else:
            # create an artificial series from last N identical points (very limited)
            # Try to fetch a small daily history via yfinance ticker.history (fallback)
            try:
                ticker = yf.Ticker(YAHOO_FUTURES_SYMBOL)
                hist = ticker.history(period="60d", interval="1d")['Close'].dropna().to_frame(name="price")
                if hist.empty or len(hist) < max(SMA_LONG, RSI_PERIOD) + 2:
                    indicators = compute_indicators_from_df(hist) if not hist.empty else {"error": "no history"}
                else:
                    indicators = compute_indicators_from_df(hist)
            except Exception as e:
                indicators = {"error": f"indicator error: {e}"}
        result["technical_indicators"] = indicators

        # 3) scrape news headlines and simple sentiment
        headlines = fetch_reuters_gold_headlines(limit=6)
        result["news_headlines"] = headlines
        sentiment = simple_sentiment_from_headlines(headlines)
        result["news_sentiment"] = sentiment

        # 4) decision
        prediction = decide_signal(indicators, sentiment)
        result["prediction"] = prediction

    # Save result JSON
    try:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✅ Pipeline finished. Results saved to: {OUTPUT_JSON}")
    except Exception as e:
        print(f"⚠️ Failed to save JSON: {e}")

    # Print compact summary
    print("\n--- XAUUSD SIGNAL SUMMARY ---")
    print(f"Time (local): {ts}")
    if result.get("price_aggregate"):
        print(f"Price (mean): {result['price_aggregate']['mean']:.4f}  (sources: {', '.join(result['price_aggregate']['sources'])})")
    else:
        print("Price: N/A")
    pred = result.get("prediction", {})
    print(f"Signal: {pred.get('signal', 'HOLD')}  Confidence: {pred.get('confidence', 0)}%")
    print("Reasons:", "; ".join(pred.get("reasons", [])))
    print("-----------------------------\n")

    LATEST_SIGNAL_FILE = Path(r"f:\cap\latest_signal.json")

    # Create dynamic new signal data
    new_signal = {
        "Signal": pred.get("signal", "HOLD"),
        "Confidence": f"{pred.get('confidence', 0)}%"
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


    DB_PATH = r"f:\cap\signals.db"

    # Connect to the database (it will be created if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table if it doesn’t exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            Chart_signal TEXT,
            signal TEXT,
            confidence TEXT,
            candle_Signal TEXT,
            candle_Confidence TEXT,
            source TEXT
        )
    """)

    # Load latest signal JSON file
    LATEST_SIGNAL_PATH = Path(r"f:\cap\latest_signal.json")
    if LATEST_SIGNAL_PATH.exists():
        with open(LATEST_SIGNAL_PATH, "r", encoding="utf-8") as f:
            latest_data = json.load(f)
    else:
        latest_data = {}

    # Prepare values from JSON
    timestamp = datetime.now().isoformat(timespec="seconds")
    Chart_signal = latest_data.get("Chart_signal", "N/A")
    signal = latest_data.get("Signal", "N/A")
    confidence = latest_data.get("Confidence", "N/A")
    candle_Signal = latest_data.get("candle_Signal", "N/A")
    candle_Confidence = latest_data.get("candle_Confidence", "N/A")
    source = "pipeline"

    # Insert new record
    cursor.execute("""
        INSERT INTO signal_history 
        (timestamp, Chart_signal, signal, confidence, candle_Signal, candle_Confidence, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, Chart_signal, signal, confidence, candle_Signal, candle_Confidence, source))

    # Commit and close
    conn.commit()
    conn.close()

    print(f"📊 Signal saved to database: {DB_PATH}")

    # --- Optional: Display latest records ---
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM signal_history ORDER BY id DESC", conn)
    conn.close()

    print(df)

    return result





if __name__ == "__main__":
    run_pipeline()
