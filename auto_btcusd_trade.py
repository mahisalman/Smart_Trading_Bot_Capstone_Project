import MetaTrader5 as mt5
import sqlite3
import time
import sys
from datetime import datetime

# ---------------------------
# 🔐 ACCOUNT CONFIGURATION
# ---------------------------
LOGIN_ID = 206426967
PASSWORD = "S@lman0193"
SERVER = "Exness-MT5Trial7"

# ---------------------------
# ⚙️ TRADE PARAMETERS
# ---------------------------
VOLUME = 0.01
SL_PRICE_DIFF = 100.00    # USD distance for SL
TP_PRICE_DIFF = 200.00    # USD distance for TP
TRADE_DEVIATION = 30
TRADE_MAGIC = 2025

# ---------------------------
# 🧩 DATABASE PATH
# ---------------------------
DB_PATH = r"f:\cap\signals.db"


# ==========================================================
# ✅ Step 1: Initialize & Login
# ==========================================================
def initialize_mt5():
    print("🔌 Initializing MetaTrader 5...")
    if not mt5.initialize():
        print(f"❌ MT5 initialization failed: {mt5.last_error()}")
        sys.exit()

    print("🔑 Logging in to account...")
    if not mt5.login(LOGIN_ID, PASSWORD, SERVER):
        print("❌ Login failed. Check credentials or server.")
        print("Error:", mt5.last_error())
        mt5.shutdown()
        sys.exit()

    print(f"✅ Logged in successfully as {LOGIN_ID} on {SERVER}")

    terminal_info = mt5.terminal_info()
    if terminal_info is not None and not terminal_info.trade_allowed:
        print("⚠️ AutoTrading is DISABLED in your MT5 terminal!")
        print("➡️ Please open MT5 and click the green 'AutoTrading' button.")
        mt5.shutdown()
        sys.exit()

    print("🟢 AutoTrading permission confirmed.")


# ==========================================================
# ✅ Step 2: Find Tradeable BTCUSD Symbol
# ==========================================================
def find_tradeable_gold_symbol():
    print("\n🔎 Searching for tradeable Gold (BTCUSD) symbols...")
    gold_symbols = mt5.symbols_get("*BTCUSD*")
    if not gold_symbols:
        print("❌ No BTCUSD symbols found.")
        mt5.shutdown()
        sys.exit()

    for sym in gold_symbols:
        info = mt5.symbol_info(sym.name)
        if info is None:
            continue
        if not info.visible:
            mt5.symbol_select(sym.name, True)
        if info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
            print(f"✅ Found tradeable Gold symbol: {sym.name}")
            return sym.name

    print("❌ No tradeable BTCUSD symbol found.")
    mt5.shutdown()
    sys.exit()


# ==========================================================
# ✅ Step 3: Read Latest Signal from Database
# ==========================================================
def get_latest_chart_signal():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, chart_signal FROM signal_history ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            signal_id, timestamp, chart_signal = row
            print(f"📊 Latest DB Signal → ID: {signal_id}, Time: {timestamp}, Chart Signal: {chart_signal}")
            return chart_signal.strip().upper()
        else:
            print("⚠️ No signals found in the database.")
            return None
    except Exception as e:
        print(f"❌ Error reading signals.db → {e}")
        return None


# ==========================================================
# ✅ Step 4: Calculate SL / TP
# ==========================================================
def calculate_sl_tp(order_type, price):
    if order_type == mt5.ORDER_TYPE_BUY:
        sl = round(price - SL_PRICE_DIFF, 2)
        tp = round(price + TP_PRICE_DIFF, 2)
    else:
        sl = round(price + SL_PRICE_DIFF, 2)
        tp = round(price - TP_PRICE_DIFF, 2)
    return sl, tp


# ==========================================================
# ✅ Step 5: Get Filling Mode (Force IOC for Exness)
# ==========================================================
def get_filling_mode(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    print(f"🧩 Supported filling modes for {symbol}: {info.filling_mode}")
    return mt5.ORDER_FILLING_IOC


# ==========================================================
# ✅ Step 6: Execute Trade
# ==========================================================
def place_trade(symbol, chart_signal):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"❌ Cannot get tick data for {symbol}.")
        return

    # Determine trade direction
    if chart_signal == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    elif chart_signal == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        print(f"⚠️ Unsupported signal '{chart_signal}' → no trade opened.")
        return

    sl, tp = calculate_sl_tp(order_type, price)
    filling_mode = get_filling_mode(symbol)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": VOLUME,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": TRADE_DEVIATION,
        "magic": TRADE_MAGIC,
        "comment": f"DB-Signal-{chart_signal}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }

    print(f"\n🚀 Executing {chart_signal} trade on {symbol}")
    print(f"   Price={price} | SL={sl} | TP={tp}")

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ Trade executed successfully at {result.price}")
        print(f"   Ticket: {result.order}")
    else:
        print(f"❌ Trade failed! Retcode={result.retcode}")
        print(f"   Details: {result}")


# ==========================================================
# ✅ Step 7: Main Entry
# ==========================================================
if __name__ == "__main__":
    initialize_mt5()
    symbol = find_tradeable_gold_symbol()

    latest_signal = get_latest_chart_signal()
    if latest_signal:
        place_trade(symbol, latest_signal)

    mt5.shutdown()
