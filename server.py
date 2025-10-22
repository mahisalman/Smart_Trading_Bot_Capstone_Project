import MetaTrader5 as mt5
import time
import sys

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
SL_PRICE_DIFF = 10.00    # Stop loss distance in USD
TP_PRICE_DIFF = 20.00    # Take profit distance in USD
TRADE_DEVIATION = 30
TRADE_MAGIC = 2025
ORDER_TYPE = mt5.ORDER_TYPE_BUY  # Change to SELL for short trades


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

    # Check if AutoTrading is allowed in the terminal
    terminal_info = mt5.terminal_info()
    if terminal_info is not None and not terminal_info.trade_allowed:
        print("⚠️ AutoTrading is DISABLED in your MT5 terminal!")
        print("➡️ Please open MT5 and click the green 'AutoTrading' button.")
        mt5.shutdown()
        sys.exit()

    print("🟢 AutoTrading permission confirmed.")


# ==========================================================
# ✅ Step 2: Detect Tradeable Gold Symbol
# ==========================================================
def find_tradeable_gold_symbol():
    print("\n🔎 Searching for available Gold (XAUUSD) symbols...")

    gold_symbols = mt5.symbols_get("*XAUUSD*")
    if not gold_symbols:
        print("❌ No XAUUSD symbols found.")
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

    print("❌ No tradeable XAUUSD symbol found!")
    mt5.shutdown()
    sys.exit()


# ==========================================================
# ✅ Step 3: SL / TP Calculation
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
# ✅ Step 4: Filling Mode Detection
# ==========================================================
def get_filling_mode(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC

    supported = []
    if info.filling_mode & mt5.ORDER_FILLING_FOK:
        supported.append("FOK")
    if info.filling_mode & mt5.ORDER_FILLING_IOC:
        supported.append("IOC")
    if info.filling_mode & mt5.ORDER_FILLING_RETURN:
        supported.append("RETURN")

    print(f"🧩 Supported filling modes for {symbol}: {supported}")

    # Force IOC for Exness reliability
    return mt5.ORDER_FILLING_IOC


# ==========================================================
# ✅ Step 5: Execute Trade
# ==========================================================
def place_trade(symbol):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"❌ Cannot get tick data for {symbol}.")
        return

    price = tick.ask if ORDER_TYPE == mt5.ORDER_TYPE_BUY else tick.bid
    sl, tp = calculate_sl_tp(ORDER_TYPE, price)
    filling_mode = get_filling_mode(symbol)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": VOLUME,
        "type": ORDER_TYPE,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": TRADE_DEVIATION,
        "magic": TRADE_MAGIC,
        "comment": "Auto-Gold-Trader",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }

    print(f"\n🚀 Sending {VOLUME} lot {'BUY' if ORDER_TYPE == 0 else 'SELL'} order for {symbol}")
    print(f"   Price={price} | SL={sl} | TP={tp} | Filling Mode={filling_mode}")

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ Trade executed successfully at {result.price}")
        print(f"   Ticket: {result.order}")
    else:
        print(f"❌ Trade failed! Retcode={result.retcode}")
        print(f"   Details: {result}")


# ==========================================================
# ✅ Step 6: Main
# ==========================================================
if __name__ == "__main__":
    initialize_mt5()
    symbol = find_tradeable_gold_symbol()
    time.sleep(1)
    place_trade(symbol)
    mt5.shutdown()
