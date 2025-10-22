import requests
import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# === CONFIG ===
SYMBOL = "XAU/USD"
INTERVAL = "1h"  # H4 timeframe
OUTPUT_FILE = "poi_signal.json"

# === API KEYS ===
TWELVE_API_KEY = "5a55f7fefadf48dc8d0a2d5685b553ba"
GITHUB_API_KEY = "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"

# === ENDPOINTS ===
TWELVE_URL = (
    f"https://api.twelvedata.com/time_series?"
    f"symbol={SYMBOL}&interval={INTERVAL}&apikey={TWELVE_API_KEY}&outputsize=100"
)
GITHUB_ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL_NAME = "openai/gpt-4.1-mini"

# === PROMPT ===
POI_PROMPT = """
You are a professional XAUUSD (Gold) trader specializing in Smart Money Concepts (SMC), market structure, and institutional price behavior.

Your task: Detect the **most recent valid Point of Interest (POI)** zone from the given OHLC data of XAUUSD.

---

### 🧩 Core Concept

A **POI (Point of Interest)** is a price zone where the market is likely to return after breaking a structure — it represents the last opposing candle before a significant move (Break of Structure).

We only consider the **most recent** structural break and its related POI.

---

### 🧱 Detection Rules

1. **Identify a Break of Structure (BOS):**
   - A BOS occurs when price **closes above** the most recent swing high (for bullish BOS)  
     or **closes below** the most recent swing low (for bearish BOS).

2. **After a Bullish Break of Structure (BOS-UP):**
   - Find the **neckline candle** — the candle that caused the upward break.
   - To the **right** of this neckline candle, locate the **lowest bullish candle** (the deepest pullback after the break).
   - To the **left** of that bullish candle, find the **first bearish candle** before it.
   - That **bearish candle** is the **POI candle**.
   - The **POI zone** is drawn from that bearish candle’s **open to wick low**.

3. **After a Bearish Break of Structure (BOS-DOWN):**
   - Find the **neckline candle** — the candle that caused the downward break.
   - To the **right** of this neckline candle, locate the **highest bearish candle** (the deepest pullback after the break).
   - To the **left** of that bearish candle, find the **first bullish candle** before it.
   - That **bullish candle** is the **POI candle**.
   - The **POI zone** is drawn from that bullish candle’s **open to wick high**.

4. **Confidence Level:**
   - **High:** if the structure break is clear and the POI candle is distinct with imbalance or displacement.
   - **Medium:** if the break is moderate or POI overlaps consolidation.
   - **Low:** if structure is unclear or overlapping.

5. **Return Output Strictly in JSON format:**
```json
{
  "BOS_Type": "Bullish" or "Bearish",
  "POI_Candle": {
    "Open": <price>,
    "High": <price>,
    "Low": <price>,
    "Close": <price>,
    "Time": "<timestamp>"
  },
  "POI_Zone": {
    "Start": <price>,  // candle open
    "End": <price>     // candle low for bullish POI, candle high for bearish POI
  },
  "Confidence": "<High | Medium | Low>",
  "Comment": "Short reasoning describing why this candle qualifies as the institutional POI zone."
}
"""


# === FETCH DATA ===
def fetch_xauusd_h4():
    print("📡 Fetching XAUUSD H4 data...")
    try:
        response = requests.get(TWELVE_URL)
        response.raise_for_status()
        data = response.json()

        if "values" not in data:
            raise Exception(f"Unexpected API response: {data}")

        candles = data["values"][::-1]  # reverse to oldest→latest
        print(f"✅ Fetched {len(candles)} candles.")
        return candles
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return []


# === ANALYZE WITH GITHUB MODEL ===
def analyze_poi_with_github_llm(candles):
    print("🧠 Sending chart data to GitHub Model for POI analysis...")
    try:
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": POI_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Here is the recent {SYMBOL} {INTERVAL} OHLC data:\n\n"
                        f"{json.dumps(candles[-50:], indent=2)}\n\n"
                        "Find and return the POI as per the above rule."
                    ),
                },
            ],
            "temperature": 0.3,
        }

        headers = {
            "Authorization": f"Bearer {GITHUB_API_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(GITHUB_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            output_text = result["choices"][0]["message"]["content"]
        elif "output" in result:
            output_text = result["output"]
        else:
            raise Exception(f"Unexpected response format: {result}")

        print("✅ Received POI analysis from GitHub Model.")
        return output_text
    except Exception as e:
        print(f"❌ Error analyzing POI: {e}")
        return None


# === SAVE TO JSON ===
def save_to_json(output_text):
    try:
        start = output_text.find("{")
        end = output_text.rfind("}") + 1
        json_text = output_text[start:end]
        data = json.loads(json_text)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"💾 POI analysis saved successfully → {OUTPUT_FILE}")
        return data
    except Exception as e:
        print(f"⚠️ Error saving JSON: {e}\nRaw Output:\n{output_text}")
        return None


# === PLOT CHART ===
def plot_chart(candles, poi_data):
    print("📊 Plotting chart with POI zone...")

    df = pd.DataFrame(candles)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title(f"{SYMBOL} ({INTERVAL}) - Latest Chart with POI", fontsize=14)
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")

    # Plot candles
    for i in range(len(df)):
        color = "green" if df["close"][i] >= df["open"][i] else "red"
        ax.plot([df["datetime"][i], df["datetime"][i]], [df["low"][i], df["high"][i]], color=color)
        ax.add_patch(plt.Rectangle(
            (mdates.date2num(df["datetime"][i]) - 0.1, min(df["open"][i], df["close"][i])),
            0.2,
            abs(df["close"][i] - df["open"][i]),
            color=color,
            alpha=0.8,
        ))

    # Highlight POI Zone
    if poi_data:
        poi_candle = poi_data.get("POI_Candle", {})
        poi_zone = poi_data.get("POI_Zone", {})
        bos_type = poi_data.get("BOS_Type", "Unknown")

        poi_time = pd.to_datetime(poi_candle.get("Time"))
        zone_start = float(poi_zone.get("Start"))
        zone_end = float(poi_zone.get("End"))

        # Draw zone
        ax.axhspan(zone_start, zone_end, color="gold", alpha=0.3, label="POI Zone")

        # Mark POI candle
        ax.scatter(poi_time, poi_candle["Close"], color="blue", s=80, label=f"POI Candle ({bos_type})")

    # Formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.show()


# === MAIN ===
def main():
    candles = fetch_xauusd_h4()
    if not candles:
        print("❌ No candle data available. Exiting.")
        return

    llm_output = analyze_poi_with_github_llm(candles)
    if llm_output:
        poi_data = save_to_json(llm_output)
        if poi_data:
            plot_chart(candles, poi_data)
    else:
        print("❌ No output received from GitHub model.")


if __name__ == "__main__":
    main()
