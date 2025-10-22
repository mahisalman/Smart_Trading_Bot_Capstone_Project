import MetaTrader5 as mt5
import sqlite3
import sys
import time
import json
import os
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
BASE_LOT = 0.01                # 🆕 Starting lot size
LOT_INCREMENT = 0.01           # 🆕 Increment each cycle
LOT_TRACK_FILE = "lot_tracker.json"  # 🆕 Persistent lot tracker

TP_PIPS = [70, 100, 150, 200, 300]
TRADE_DEVIATION = 30
TRADE_MAGIC = 2025
DB_PATH = r"f:\cap\signals.db"
BREAKEVEN_BUFFER = 5  # pips buffer for breakeven

# ==============================
# ✅ MT5 Initialization
# ==============================
def initialize_mt5():
    print("🔌 Initializing MT5...")
    if not mt5.initialize():
        print(f"❌ MT5 init failed: {mt5.last_error()}")
        sys.exit()

    print("🔑 Logging in...")
    if not mt5.login(LOGIN_ID, PASSWORD, SERVER):
        print(f"❌ Login failed: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit()
    
    term_info = mt5.terminal_info()
    if not term_info or not term_info.trade_allowed:
        print("⚠️ AutoTrading disabled or terminal info unavailable!")
        mt5.shutdown()
        sys.exit()
    
    print("✅ MT5 ready.")

# ==============================
# ✅ Database Signal Fetch
# ==============================
def get_latest_chart_signal():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chart_signal FROM signal_history ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        return row[0].strip().upper() if row and row[0] is not None else None
    except Exception as e:
        print(f"❌ DB read error: {e}")
        return None

# ==============================
# ✅ Symbol Detection
# ==============================
def find_tradeable_gold_symbol():
    symbols = mt5.symbols_get("*XAUUSD*")
    for s in symbols or []:
        info = mt5.symbol_info(s.name)
        if info and not info.visible:
            mt5.symbol_select(s.name, True)
            info = mt5.symbol_info(s.name)
        if info and info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
            return s.name
    print("❌ No tradeable XAUUSD found.")
    mt5.shutdown()
    sys.exit()

# ==============================
# ✅ Helper: pip value
# ==============================
def get_pip_value(symbol):
    info = mt5.symbol_info(symbol)
    if not info:
        return 0.1, 2
    if "JPY" in symbol:
        return 0.01, info.digits
    elif "XAU" in symbol or "XAG" in symbol:
        return 0.1, info.digits
    else:
        return 0.0001, info.digits

# ==============================
# 🆕 Dynamic Lot Management
# ==============================
def load_lot_size():
    if os.path.exists(LOT_TRACK_FILE):
        with open(LOT_TRACK_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_lot", BASE_LOT)
    return BASE_LOT

def save_lot_size(new_lot):
    with open(LOT_TRACK_FILE, "w") as f:
        json.dump({"last_lot": round(new_lot, 2)}, f)

def get_dynamic_lot(symbol):
    """Increase lot by +0.01 only when all trades are fully closed"""
    positions = mt5.positions_get(symbol=symbol) or []
    orders = mt5.orders_get(symbol=symbol) or []

    last_lot = load_lot_size()
    if not positions and not orders:
        # all trades closed, increment
        new_lot = round(last_lot + LOT_INCREMENT, 2)
        save_lot_size(new_lot)
        print(f"📈 All trades closed — lot increased to {new_lot}")
        return new_lot
    else:
        # keep previous
        return last_lot

# ==============================
# ✅ Check for active trades for this signal
# ==============================
def has_active_signal_trades(symbol, signal):
    positions = mt5.positions_get(symbol=symbol) or []
    orders = mt5.orders_get(symbol=symbol) or []
    for pos in positions:
        if pos.comment == f"DB-Signal-{signal}" and pos.magic == TRADE_MAGIC:
            return True
    for order in orders:
        if order.comment == f"DB-Signal-{signal}" and order.magic == TRADE_MAGIC:
            return True
    return False

# ==============================
# ✅ Open multiple trades
# ==============================
def open_multiple_trades(symbol, signal):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("❌ Cannot fetch tick data.")
        return

    if has_active_signal_trades(symbol, signal):
        print(f"⚠️ Existing {signal} trades detected — waiting for them to close.")
        return

    pip, digits = get_pip_value(symbol)
    direction = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
    price = float(tick.ask) if signal == "BUY" else float(tick.bid)

    dynamic_lot = get_dynamic_lot(symbol)  # 🆕 Use dynamic lot
    print(f"🚀 Opening {len(TP_PIPS)} {signal} trades | Lot={dynamic_lot} | Price={price}")

    for i, tp_pips in enumerate(TP_PIPS):
        tp_offset = tp_pips * pip
        tp_price = price + tp_offset if signal == "BUY" else price - tp_offset
        tp_price = round(tp_price, digits)

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": dynamic_lot,
            "type": direction,
            "price": price,
            "sl": 0.0,
            "tp": tp_price,
            "deviation": TRADE_DEVIATION,
            "magic": TRADE_MAGIC,
            "comment": f"DB-Signal-{signal}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ Trade {i+1} opened | TP={tp_price} | ticket={res.order}")
        else:
            print(f"❌ Trade {i+1} failed | {res}")

# ==============================
# ✅ Close opposite trades
# ==============================
def close_opposite_trades(symbol, signal):
    opposite = "SELL" if signal == "BUY" else "BUY"
    positions = mt5.positions_get(symbol=symbol) or []
    for pos in positions:
        try:
            if pos.comment == f"DB-Signal-{opposite}" and pos.magic == TRADE_MAGIC:
                close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    continue
                price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "price": price,
                    "deviation": TRADE_DEVIATION,
                    "magic": TRADE_MAGIC,
                    "comment": f"Close-Opposite-{opposite}",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC
                }
                res = mt5.order_send(req)
                print(f"✅ Closed opposite {opposite} trade (ticket={pos.ticket}) | {res.retcode}")
        except Exception as e:
            print(f"⚠️ Error closing opposite: {e}")

# ==============================
# ✅ Breakeven Logic
# ==============================
def adjust_breakeven(symbol, signal):
    """Move SL to breakeven after +70 pips"""
    positions = mt5.positions_get(symbol=symbol) or []
    if not positions:
        return

    pip, digits = get_pip_value(symbol)
    threshold_pips = 70

    for pos in positions:
        if pos.comment != f"DB-Signal-{signal}" or pos.magic != TRADE_MAGIC:
            continue

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
        entry = pos.price_open
        direction = pos.type
        current = tick.bid if direction == mt5.ORDER_TYPE_BUY else tick.ask

        threshold = entry + threshold_pips * pip if direction == mt5.ORDER_TYPE_BUY else entry - threshold_pips * pip
        new_sl = entry + BREAKEVEN_BUFFER * pip if direction == mt5.ORDER_TYPE_BUY else entry - BREAKEVEN_BUFFER * pip

        if (direction == mt5.ORDER_TYPE_BUY and current >= threshold) or \
           (direction == mt5.ORDER_TYPE_SELL and current <= threshold):
            sl_current = float(pos.sl or 0.0)
            if (direction == mt5.ORDER_TYPE_BUY and sl_current < new_sl) or \
               (direction == mt5.ORDER_TYPE_SELL and (sl_current == 0.0 or sl_current > new_sl)):
                mod = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "sl": round(new_sl, digits),
                    "tp": pos.tp
                }
                result = mt5.order_send(mod)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"🔧 SL moved to breakeven | Ticket={pos.ticket} | New SL={round(new_sl, digits)}")
                else:
                    print(f"⚠️ SL move failed | Ticket={pos.ticket} | Code={result.retcode}")

# ==============================
# ✅ Main Execution
# ==============================
# if __name__ == "__main__":
#     initialize_mt5()
#     symbol = find_tradeable_gold_symbol()
#     signal = get_latest_chart_signal()

#     if signal:
#         print(f"📊 Latest Signal: {signal}")
#         close_opposite_trades(symbol, signal)
#         open_multiple_trades(symbol, signal)

#         print("⏱ Monitoring trades for breakeven (5 min)...")
#         start = time.time()
#         while time.time() - start < 5 * 60:
#             adjust_breakeven(symbol, signal)
#             time.sleep(10)

#     mt5.shutdown()
#     print("✅ EA Finished.")
