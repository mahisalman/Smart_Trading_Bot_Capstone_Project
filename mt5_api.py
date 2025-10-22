#!python
"""
mt5_api.py

Lightweight local HTTP API to control an open MetaTrader 5 terminal.

Usage:
    1. Start MT5 and log into your broker (demo recommended for tests).
    2. Install dependencies: pip install MetaTrader5 Flask pandas
    3. Start this script: python mt5_api.py
    4. Send POST /trade JSON commands (see examples below).

Features:
- Connects to MT5 terminal via MetaTrader5 Python package.
- Minimal safety checks: symbol selection, volume bounds, margin check.
- Dry-run mode to test without sending orders.
- Endpoints:
    POST /trade    -> open market order
    POST /close    -> close open position by ticket or symbol
    GET  /positions-> list current positions
    GET  /account  -> account info
"""

import json
import logging
import sys
from datetime import datetime
from math import isclose

from flask import Flask, request, jsonify
import MetaTrader5 as mt5
import pandas as pd

# ---------- USER CONFIG ----------
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 5000
MAGIC = 987654
DEVIATION = 20  # max slippage in points
DRY_RUN = True  # set True to simulate orders (no real orders)
# ---------------------------------

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("mt5_api")

app = Flask(__name__)


# -----------------------------
# MT5 helper utilities
# -----------------------------
def init_mt5():
    """Initialize connection to MT5 terminal"""
    if not mt5.initialize():
        err = mt5.last_error()
        logger.error("mt5.initialize() failed: %s", err)
        raise RuntimeError(f"Failed to initialize MT5: {err}")
    logger.info("Connected to MetaTrader 5 (terminal).")


def shutdown_mt5():
    mt5.shutdown()
    logger.info("MT5 shutdown.")


def require_symbol(symbol: str):
    """Ensure the symbol is visible/selected in MT5"""
    if not mt5.symbol_select(symbol, True):
        return False, f"symbol_select failed for {symbol}"
    return True, ""


def is_volume_ok(symbol_info, volume: float):
    """Check volume within allowed min/max and step"""
    try:
        vmin = float(symbol_info.volume_min)
        vmax = float(symbol_info.volume_max)
        step = float(symbol_info.volume_step)
        if volume < vmin or volume > vmax:
            return False, f"volume {volume} outside [{vmin},{vmax}]"
        # check multiple of step (within tolerance)
        # compute nearest step
        n = round((volume - vmin) / step)
        expected = vmin + n * step
        if not isclose(expected, volume, rel_tol=1e-9, abs_tol=1e-9):
            return False, f"volume {volume} not a multiple of step {step}"
        return True, ""
    except Exception as e:
        return False, f"volume check error: {e}"


def can_afford(symbol: str, order_type: int, volume: float, price: float):
    """Use mt5.order_calc_margin to estimate margin and compare with free margin"""
    try:
        margin = mt5.order_calc_margin(order_type, symbol, volume, price)
        info = mt5.account_info()
        if info is None:
            return False, "failed to fetch account_info"
        free = float(info.margin_free)
        if margin is None:
            return False, "failed to calculate margin"
        if free < margin:
            return False, f"not enough free margin: need {margin:.2f}, have {free:.2f}"
        return True, ""
    except Exception as e:
        return False, f"margin check error: {e}"


# -----------------------------
# Order / trading operations
# -----------------------------
def build_order_request(symbol: str, action: str, volume: float, tp: float = 0.0, sl: float = 0.0, comment: str = ""):
    """Construct an MT5 order_send request dict"""
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None:
        raise RuntimeError("symbol tick/info unavailable")

    if action.upper() == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = float(tick.ask)
    elif action.upper() == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = float(tick.bid)
    else:
        raise ValueError("action must be BUY or SELL")

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": price,
        "sl": float(sl) if sl else 0.0,
        "tp": float(tp) if tp else 0.0,
        "deviation": int(DEVIATION),
        "magic": int(MAGIC),
        "comment": comment or f"mt5_api_{datetime.utcnow().isoformat()}",
        # choose a filling type that the broker supports
        "type_filling": mt5.ORDER_FILLING_FOK if info.trade_filling_mode == mt5.ORDER_FILLING_FOK else mt5.ORDER_FILLING_IOC,
    }
    return req


def send_order(req: dict):
    """Send order (or simulate if DRY_RUN). Returns result dict."""
    if DRY_RUN:
        logger.info("[DRY_RUN] would send order: %s", req)
        return {"simulated": True, "request": req}

    result = mt5.order_send(req)
    if result is None:
        err = mt5.last_error()
        logger.error("order_send returned None, last_error=%s", err)
        return {"success": False, "error": str(err)}
    # result has attributes: retcode, comment, request, deal, order, volume_remaining...
    ok = (result.retcode == mt5.TRADE_RETCODE_DONE or getattr(result, "retcode", None) == mt5.TRADE_RETCODE_DONE_REMAINDER)
    return {
        "success": ok,
        "retcode": int(result.retcode) if hasattr(result, "retcode") else None,
        "details": result._asdict() if hasattr(result, "_asdict") else str(result)
    }


def close_position_by_ticket(ticket: int):
    """Close a single position by ticket id (market opposite order)."""
    pos = mt5.positions_get(ticket=ticket)
    if pos is None or len(pos) == 0:
        return {"success": False, "error": f"position {ticket} not found"}
    p = pos[0]
    symbol = p.symbol
    volume = float(p.volume)
    # determine opposite type
    if p.type == mt5.POSITION_TYPE_BUY:
        typ = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        typ = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask

    close_req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": typ,
        "position": int(ticket),
        "price": float(price),
        "deviation": int(DEVIATION),
        "magic": MAGIC,
        "comment": f"close_by_ticket_{ticket}"
    }

    if DRY_RUN:
        return {"simulated": True, "request": close_req}
    res = mt5.order_send(close_req)
    if res is None:
        return {"success": False, "error": str(mt5.last_error())}
    return {"success": res.retcode == mt5.TRADE_RETCODE_DONE, "retcode": int(res.retcode), "details": res._asdict()}


def close_positions_by_symbol(symbol: str):
    """Close all positions for a symbol (one-by-one)."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None or len(positions) == 0:
        return {"success": False, "error": f"no positions for {symbol}"}

    results = []
    for p in positions:
        ticket = p.ticket
        r = close_position_by_ticket(ticket)
        results.append({"ticket": ticket, "result": r})
    return {"success": True, "results": results}


# -----------------------------
# Flask API endpoints
# -----------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})


@app.route("/account", methods=["GET"])
def account():
    ai = mt5.account_info()
    if ai is None:
        return jsonify({"success": False, "error": "failed to fetch account_info", "last_error": mt5.last_error()})
    data = {k: getattr(ai, k) for k in ai._fields}
    return jsonify({"success": True, "account_info": data})


@app.route("/positions", methods=["GET"])
def positions():
    pos = mt5.positions_get()
    if pos is None:
        return jsonify({"success": True, "positions": []})
    rows = []
    for p in pos:
        rows.append({k: getattr(p, k) for k in p._fields})
    return jsonify({"success": True, "positions": rows})


@app.route("/trade", methods=["POST"])
def api_trade():
    """
    POST /trade
    JSON params:
    {
      "symbol": "XAUUSD",
      "action": "BUY" or "SELL",
      "volume": 0.01,
      "tp": 2280.0,   # optional
      "sl": 2260.0,   # optional
      "comment": "optional note"
    }
    """
    payload = request.get_json(force=True)
    required = ["symbol", "action", "volume"]
    for r in required:
        if r not in payload:
            return jsonify({"success": False, "error": f"missing param: {r}"}), 400

    symbol = str(payload["symbol"]).upper()
    action = str(payload["action"]).upper()
    volume = float(payload["volume"])
    tp = float(payload.get("tp", 0.0) or 0.0)
    sl = float(payload.get("sl", 0.0) or 0.0)
    comment = str(payload.get("comment", ""))

    # validate symbol
    ok, msg = require_symbol(symbol)
    if not ok:
        return jsonify({"success": False, "error": msg}), 400

    # refresh symbol info / ticks
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        return jsonify({"success": False, "error": "symbol info/tick unavailable"}), 500

    # check volume
    ok, msg = is_volume_ok(info, volume)
    if not ok:
        return jsonify({"success": False, "error": msg}), 400

    # build request
    try:
        req = build_order_request(symbol, action, volume, tp, sl, comment)
    except Exception as e:
        return jsonify({"success": False, "error": f"failed to build request: {e}"}), 500

    # margin check
    ok, msg = can_afford(symbol, req["type"], volume, req["price"])
    if not ok:
        return jsonify({"success": False, "error": msg}), 400

    # send/order
    res = send_order(req)
    return jsonify(res)


@app.route("/close", methods=["POST"])
def api_close():
    """
    POST /close
    JSON params:
    either {"ticket": 12345} or {"symbol": "XAUUSD"}
    """
    payload = request.get_json(force=True)
    if "ticket" in payload:
        try:
            ticket = int(payload["ticket"])
        except Exception:
            return jsonify({"success": False, "error": "ticket must be integer"}), 400
        res = close_position_by_ticket(ticket)
        return jsonify(res)
    elif "symbol" in payload:
        symbol = str(payload["symbol"]).upper()
        res = close_positions_by_symbol(symbol)
        return jsonify(res)
    else:
        return jsonify({"success": False, "error": "need ticket or symbol field"}), 400


# -----------------------------
# Main entrypoint
# -----------------------------
def main():
    logger.info("Starting MT5 API server (DRY_RUN=%s) ...", DRY_RUN)
    try:
        init_mt5()
    except Exception as e:
        logger.exception("Failed to init MT5: %s", e)
        sys.exit(1)

    try:
        app.run(host=LISTEN_HOST, port=LISTEN_PORT, debug=False)
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
