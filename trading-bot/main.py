
import asyncio
import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path

import httpx
import websockets


# ============================================================
# CONFIGURATION — PAPER TRADING ONLY
# ============================================================

SYMBOL = "BTCUSDT"
INTERVAL = "1m"

REST_URL = "https://api.binance.com/api/v3/klines"
WS_URL = (
    "wss://stream.binance.com:9443/ws/"
    f"{SYMBOL.lower()}@kline_{INTERVAL}"
)

DB_PATH = Path("data/trading.db")

PAPER_ONLY = True  # Safety invariant; no live-order adapter exists.

STARTING_CASH = 1_000.00
TRADE_USD = 50.00
MAX_ORDER_USD = 100.00
MAX_POSITION_BTC = 0.01

FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005

FAST_WINDOW = 5
SLOW_WINDOW = 20

RECONNECT_SECONDS = 5
MAX_STALE_SECONDS = 180

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("paper-bot")


# ============================================================
# DATABASE
# ============================================================

def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    db.executescript("""
        CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            close_time INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY(symbol, interval, open_time)
        );

        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            cash REAL NOT NULL,
            btc REAL NOT NULL,
            avg_entry REAL NOT NULL,
            realized_pnl REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS paper_orders (
            order_id TEXT PRIMARY KEY,
            candle_time INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            reference_price REAL NOT NULL,
            fill_price REAL NOT NULL,
            fee REAL NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS processed_candles (
            open_time INTEGER PRIMARY KEY
        );
    """)

    db.execute("""
        INSERT OR IGNORE INTO account
            (id, cash, btc, avg_entry, realized_pnl)
        VALUES (1, ?, 0, 0, 0)
    """, (STARTING_CASH,))

    db.commit()
    return db


# ============================================================
# MARKET DATA
# ============================================================

def normalize_rest(row):
    return {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "open_time": int(row[0]),
        "close_time": int(row[6]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
    }


def normalize_ws(message):
    k = message["k"]

    return {
        "symbol": k["s"],
        "interval": k["i"],
        "open_time": int(k["t"]),
        "close_time": int(k["T"]),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
    }


def save_candle(db, candle):
    db.execute("""
        INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, interval, open_time)
        DO UPDATE SET
            close_time=excluded.close_time,
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume
    """, (
        candle["symbol"],
        candle["interval"],
        candle["open_time"],
        candle["close_time"],
        candle["open"],
        candle["high"],
        candle["low"],
        candle["close"],
        candle["volume"],
    ))
    db.commit()


async def fetch_candles(client, start_time=None):
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": 1000,
    }

    if start_time is not None:
        params["startTime"] = start_time

    response = await client.get(REST_URL, params=params)
    response.raise_for_status()

    now_ms = int(time.time() * 1000)

    # Exclude the currently forming candle.
    return [
        normalize_rest(row)
        for row in response.json()
        if int(row[6]) < now_ms
    ]


async def backfill(db, client):
    candles = await fetch_candles(client)

    for candle in candles:
        save_candle(db, candle)

    # Seed history, but don't trade historical signals on startup.
    latest = db.execute("""
        SELECT MAX(open_time) AS t FROM candles
        WHERE symbol=? AND interval=?
    """, (SYMBOL, INTERVAL)).fetchone()["t"]

    log.info("Backfilled %d completed candles.", len(candles))
    return latest


async def recover_missing_candles(db, client, candle):
    """Fetch any completed candles missed during a disconnect."""
    row = db.execute("""
        SELECT MAX(open_time) AS t FROM candles
        WHERE symbol=? AND interval=?
    """, (SYMBOL, INTERVAL)).fetchone()

    latest = row["t"]

    if latest is not None and candle["open_time"] > latest + 60_000:
        log.warning("Data gap detected. Recovering missing candles.")

        missing = await fetch_candles(
            client, start_time=latest + 60_000
        )

        for item in missing:
            if item["open_time"] < candle["open_time"]:
                save_candle(db, item)


# ============================================================
# STRATEGY — SIMPLE TEST STRATEGY
# ============================================================

def get_signal(db, current_candle):
    """
    Detect a fast/slow moving-average crossover.

    The previous averages exclude the current candle.
    The current averages include it.
    """
    rows = db.execute("""
        SELECT open_time, close FROM candles
        WHERE symbol=? AND interval=? AND open_time <= ?
        ORDER BY open_time DESC
        LIMIT ?
    """, (
        SYMBOL,
        INTERVAL,
        current_candle["open_time"],
        SLOW_WINDOW + 1,
    )).fetchall()

    rows = list(reversed(rows))

    if len(rows) < SLOW_WINDOW + 1:
        return "HOLD"

    # The latest row is the current completed candle.
    previous = [float(r["close"]) for r in rows[:-1]]
    current = [float(r["close"]) for r in rows]

    previous_fast = sum(previous[-FAST_WINDOW:]) / FAST_WINDOW
    previous_slow = sum(previous[-SLOW_WINDOW:]) / SLOW_WINDOW

    current_fast = sum(current[-FAST_WINDOW:]) / FAST_WINDOW
    current_slow = sum(current[-SLOW_WINDOW:]) / SLOW_WINDOW

    if (
        previous_fast <= previous_slow
        and current_fast > current_slow
    ):
        return "BUY"

    if (
        previous_fast >= previous_slow
        and current_fast < current_slow
    ):
        return "SELL"

    return "HOLD"


# ============================================================
# PAPER EXECUTION — NO EXCHANGE ORDER CAPABILITY
# ============================================================

class PaperBroker:
    def __init__(self, db):
        self.db = db

    def account(self):
        return self.db.execute(
            "SELECT * FROM account WHERE id=1"
        ).fetchone()

    def execute(self, side, quantity, reference_price, candle_time):
        if not PAPER_ONLY:
            raise RuntimeError(
                "Safety invariant failed: paper-only mode is required."
            )

        side = side.upper()

        if side not in {"BUY", "SELL"}:
            raise ValueError("Invalid order side.")

        if quantity <= 0 or reference_price <= 0:
            raise ValueError("Quantity and price must be positive.")

        # Conservative simulated market-order slippage.
        fill_price = reference_price * (
            1 + SLIPPAGE_RATE
            if side == "BUY"
            else 1 - SLIPPAGE_RATE
        )

        notional = quantity * fill_price
        fee = notional * FEE_RATE
        account = self.account()

        reason = "Paper fill"
        status = "FILLED"

        if notional > MAX_ORDER_USD:
            status, reason = "REJECTED", "Order exceeds USD limit"

        elif side == "BUY":
            if account["btc"] + quantity > MAX_POSITION_BTC:
                status, reason = (
                    "REJECTED", "Maximum BTC position exceeded"
                )
            elif notional + fee > account["cash"]:
                status, reason = (
                    "REJECTED", "Insufficient simulated cash"
                )

        elif side == "SELL":
            if quantity > account["btc"] + 1e-12:
                status, reason = (
                    "REJECTED", "Insufficient BTC position"
                )

        # Each order and its account changes commit atomically.
        self.db.execute("BEGIN IMMEDIATE")

        try:
            if status == "FILLED":
                if side == "BUY":
                    new_cash = account["cash"] - notional - fee
                    new_btc = account["btc"] + quantity

                    # Average cost includes buy fees.
                    new_avg_entry = (
                        account["btc"] * account["avg_entry"]
                        + notional + fee
                    ) / new_btc

                    realized = account["realized_pnl"]

                else:
                    new_cash = account["cash"] + notional - fee
                    new_btc = max(0.0, account["btc"] - quantity)

                    realized = (
                        account["realized_pnl"]
                        + quantity * (fill_price - account["avg_entry"])
                        - fee
                    )

                    new_avg_entry = (
                        0.0 if new_btc < 1e-12
                        else account["avg_entry"]
                    )

                self.db.execute("""
                    UPDATE account
                    SET cash=?, btc=?, avg_entry=?, realized_pnl=?
                    WHERE id=1
                """, (
                    new_cash,
                    new_btc,
                    new_avg_entry,
                    realized,
                ))

            order_id = str(uuid.uuid4())

            self.db.execute("""
                INSERT INTO paper_orders VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                order_id,
                candle_time,
                SYMBOL,
                side,
                quantity,
                reference_price,
                fill_price,
                fee,
                status,
                reason,
            ))

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        log.info(
            "ORDER %s | %s | qty=%g | fill=%.2f | "
            "fee=%.4f | %s | %s",
            order_id,
            side,
            quantity,
            fill_price,
            fee,
            status,
            reason,
        )

        return status


# ============================================================
# RISK + PORTFOLIO
# ============================================================

def portfolio_snapshot(broker, market_price):
    account = broker.account()

    market_value = account["btc"] * market_price
    equity = account["cash"] + market_value

    unrealized = (
        account["btc"] * (market_price - account["avg_entry"])
    )

    total_pnl = equity - STARTING_CASH

    log.info(
        "PORTFOLIO | cash=$%.2f | BTC=%.8f | "
        "equity=$%.2f | unrealized P&L=$%.2f | "
        "realized P&L=$%.2f | total P&L=$%.2f",
        account["cash"],
        account["btc"],
        equity,
        unrealized,
        account["realized_pnl"],
        total_pnl,
    )


def process_candle(db, broker, candle):
    # Ignore candles that have already been processed.
    inserted = db.execute("""
        INSERT OR IGNORE INTO processed_candles(open_time)
        VALUES (?)
    """, (candle["open_time"],))

    if inserted.rowcount == 0:
        db.commit()
        return

    save_candle(db, candle)

    signal = get_signal(db, candle)
    price = candle["close"]

    log.info(
        "CANDLE CLOSED | close=%.2f | signal=%s",
        price,
        signal,
    )

    account = broker.account()

    if signal == "BUY" and account["btc"] < 1e-12:
        # Approximate BTC quantity for a $50 paper order.
        quantity = TRADE_USD / price

        broker.execute(
            "BUY", quantity, price, candle["open_time"]
        )

    elif signal == "SELL" and account["btc"] > 1e-12:
        # Close the current spot position.
        broker.execute(
            "SELL",
            account["btc"],
            price,
            candle["open_time"],
        )

    portfolio_snapshot(broker, price)
    db.commit()


# ============================================================
# MAIN LOOP
# ============================================================

async def main():
    if not PAPER_ONLY:
        raise RuntimeError("This program is paper-only.")

    db = connect_db()
    broker = PaperBroker(db)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await backfill(db, client)

            while True:
                try:
                    log.info("Connecting to public market feed...")

                    async with websockets.connect(
                        WS_URL,
                        ping_interval=20,
                        ping_timeout=20,
                        close_timeout=10,
                    ) as ws:
                        log.info(
                            "Connected. Waiting for completed candles."
                        )

                        async for raw in ws:
                            message = json.loads(raw)

                            if "k" not in message:
                                continue

                            k = message["k"]

                            if not k.get("x", False):
                                continue

                            candle = normalize_ws(message)

                            await recover_missing_candles(
                                db, client, candle
                            )

                            process_candle(db, broker, candle)

                except asyncio.CancelledError:
                    raise

                except Exception:
                    log.exception(
                        "Market feed error. Reconnecting in %s seconds.",
                        RECONNECT_SECONDS,
                    )
                    await asyncio.sleep(RECONNECT_SECONDS)

    finally:
        db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped. Paper account is saved in SQLite.")
