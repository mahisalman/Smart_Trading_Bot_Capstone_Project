from chart_flow import run_chrome_shot, image_to_base64, find_latest_signal_llm, save_signal_to_json
from pipeline import (
    fetch_price_yahoo_futures,
    fetch_price_tradingview_snapshot,
    fetch_price_kitco,
    aggregate_price_samples,
    fetch_reuters_gold_headlines,
    simple_sentiment_from_headlines,
    compute_indicators_from_df,
    decide_signal,
    run_pipeline
)
# 🧩 Import MT5 trading functions
from auto_gold_trader_db import (
    initialize_mt5,
    find_tradeable_gold_symbol,
    get_latest_chart_signal,
    place_trade,
    time,
    mt5
)

from auto_gold_5_trades import (
    initialize_mt5,
    find_tradeable_gold_symbol,
    get_latest_chart_signal,
    open_multiple_trades,
    close_opposite_trades,
    adjust_breakeven,
    mt5    
)

# ----------------------------
# 🖼️ Chart Flow Analysis
# ----------------------------
run_chrome_shot()
IMG_PATH = "firefox_tab_capture.png"
image64 = image_to_base64(IMG_PATH)
if image64 is not None:
    signal = find_latest_signal_llm(image64)
    print(f"Chart_Signal: {signal}")
    save_signal_to_json(signal)
else:
    print("Failed to convert image to Base64.")


def run_auto_trade():
    """Run the gold auto trader using the latest DB signal."""
    initialize_mt5()
    symbol = find_tradeable_gold_symbol()
    latest_signal = get_latest_chart_signal()

    if latest_signal:
        place_trade(symbol, latest_signal)
    else:
        print("⚠️ No trade executed due to missing signal.")

    mt5.shutdown()


def main():
    """Pipeline + auto-trade system for XAUUSD."""
    yahoo_data = fetch_price_yahoo_futures()
    tv_data = fetch_price_tradingview_snapshot()
    kitco_data = fetch_price_kitco()

    price_samples = [d for d in [yahoo_data, tv_data, kitco_data] if d]
    if price_samples:
        aggregated = aggregate_price_samples(price_samples)
        print("\nAggregated Price:", aggregated)
    else:
        print("\nNo price samples available to aggregate.")

    headlines = fetch_reuters_gold_headlines(limit=6)
    sentiment_score = simple_sentiment_from_headlines(headlines)

    if yahoo_data and "df" in yahoo_data:
        df_for_indicators = yahoo_data["df"]
        indicators = compute_indicators_from_df(df_for_indicators)
        print("\nTechnical indicators:", indicators)
    else:
        indicators = None
        print("\nInsufficient price data for technical indicators.")

    if indicators:
        prediction = decide_signal(indicators, sentiment_score)
        print("\nSignal decision:", prediction)
    else:
        prediction = {"signal": "HOLD", "confidence": 10, "reasons": ["insufficient data"]}
        print("\nSignal decision:", prediction)

    pipeline_result = run_pipeline()
    print("\nFull pipeline completed. JSON and DB updated.")

    # 7️⃣ Run auto gold trade
    # print("\n💰 Running Auto Gold Trader...")
    # run_auto_trade()

    return pipeline_result





if __name__ == "__main__":
    main()



if __name__ == "__main__":
    initialize_mt5()
    symbol = find_tradeable_gold_symbol()
    signal = get_latest_chart_signal()

    if signal:
        print(f"📊 Latest Signal: {signal}")
        close_opposite_trades(symbol, signal)
        open_multiple_trades(symbol, signal)

        print("⏱ Monitoring trades for breakeven (5 min)...")
        start = time.time()
        while time.time() - start < 5 * 60:
            adjust_breakeven(symbol, signal)
            time.sleep(10)

    mt5.shutdown()
    print("✅ EA Finished.")


mt5.shutdown()