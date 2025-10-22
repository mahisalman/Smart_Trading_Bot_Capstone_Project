# Smart Trading Bot – Capstone Project

Automated Trading Assistant for XAUUSD (Gold) and Other Instruments

🔍 Overview

This project is a full-stack automated trading system developed as a capstone for financial algorithmic trading and Smart Money Concepts (SMC). It is designed to trade instruments such as XAUUSD (Gold) and adapt to other markets via modular architecture.
It covers the full lifecycle: signal detection from your database, trade execution through MetaTrader 5, position management (multiple take-profits & breakeven logic), and risk/lot-size management with automatic escalation.

📂 Key Components

main.py – Entry point script that integrates signal fetching, decision logic and execution workflow.

auto_gold_trader_db.py – Handles database-driven signal reading, trade duplication prevention, multi-TP trade entry and breakeven logic.

mt5_api.py – Abstraction layer for MetaTrader 5 connections, symbol selection, and order management.

pipeline.py – Orchestrates the end-to-end pipeline (signal → trade → monitor) for automated running.

lot_tracker.json – A lightweight persistent tracker for dynamic lot size escalation logic.

requirements.txt – Lists Python dependencies (MetaTrader5, SQLite3, etc.).

.gitignore – Excludes large binaries, datasets and sensitive files from version control.

💡 Features

Database-driven signals: Reads latest trade signal from a SQLite database (signal_history) and acts accordingly.

Single trade-set per signal: Prevents duplicate execution by tracking magic number + comment context.

Dynamic lot size escalation: Every time all trades are closed successfully, lot size increments automatically.

Multi-take-profit entries: Opens multiple trades (TP70, TP100, TP150, etc) for each signal to scale and spread risk.

Breakeven logic: Moves stop-loss to breakeven + buffer after first target hit or after defined pip threshold.

Structure break & SMC ready: Designed to align with Smart Money Concepts — you can plug in POI detection modules or AI prompts.

MetaTrader 5 integration: Fully compatible with MT5 brokers; symbol selection, login, and trade API wrapped.

Clean history workflow: Includes Git history cleanup script to remove overly large files (.rar, datasets) and ensures stable repo size.

🧠 Installation & Setup
Prerequisites

Python 3.8+

MetaTrader 5 installed and broker account credentials set

SQLite3 database with table signal_history (timestamp, chart_signal) prepared

Installation
```git clone https://github.com/mahisalman/Smart_Trading_Bot_Capstone_Project.git  
cd Smart_Trading_Bot_Capstone_Project  
pip install -r requirements.txt  
```

Configuration

Edit configuration variables at top of main.py or in config section:
```LOGIN_ID = …  
PASSWORD = "…"  
SERVER = "Exness-MT5Trial7"  
LOT_SIZE (base) = 0.01  
TP_PIPS = [70, 100, 150, 200, 300]  
TRADE_MAGIC = 2025  
DB_PATH = r"f:\cap\signals.db"  
```

Running the Bot

```python main.py  
```

This will:

Connect to MT5 and login

Fetch latest signal from SQLite

Close any opposite trades for the symbol

If no active trade set exists for current signal → open multi-TP trades with dynamic lot size

Monitor trades for breakeven logic (e.g., for 5–10 minutes)

Shutdown cleanly

📝 Usage Notes & Best Practices

Back-testing first: Always test with demo accounts before going live.

Broker compatibility: Ensure the symbol (e.g., XAUUSD) trade mode is full (SYMBOL_TRADE_MODE_FULL).

Risk management: Adjust lot size and TP pips according to account size and risk tolerance.

Monitoring: Although automation is built in, periodic supervision of trades and MT5 terminal status is advisable.

Logging & audits: Integrate or extend logging (file or DB) for opened/closed trades, lot escalation, and signals processed.

Follow repository hygiene: Large files such as .rar, datasets, model weights must be excluded via .gitignore to prevent GitHub rejections.

🧪 Future Enhancements

Integrate live POI (Point of Interest) detection via AI/LLM for structure-based trade entry

Expand to multi-symbol/multi-timeframe support

Auto-adjust lot size based on performance (win/loss tracking)

Web dashboard for trade monitoring and metrics visualization

Deploy as a Docker container for cloud-based execution

📚 License

This project is released under the MIT License — feel free to modify and redistribute with attribution.

🤝 Contribution

Contributions, pull requests, and forks are welcome. Please open an issue to propose major changes or enhancements. Let’s build robust automation together.
