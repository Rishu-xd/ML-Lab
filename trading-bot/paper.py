
import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path("data/market.db")

STARTING_CASH = 1_000.00
MAX_ORDER_USD = 110.00
MAX_POSITION_BTC = 0.01

FEE_RATE = 0.001       # Simulated 0.10% fee
SLIPPAGE_RATE = 0.0005  # Simulated 0.05% slippage


class PaperBroker:
    def __init__(self):
        Path("data").mkdir(exist_ok=True)
        self.db = sqlite3.connect(DB_PATH)
        self.cash = STARTING_CASH
        self.btc = 0.0

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS paper_orders (
                order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                reference_price REAL NOT NULL,
                fill_price REAL NOT NULL,
                fee REAL NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)
        self.db.commit()

    def submit_market_order(self, side, quantity, reference_price):
        side = side.upper()

        if side not in {"BUY", "SELL"}:
            raise ValueError("Only BUY and SELL are supported.")

        if quantity <= 0 or reference_price <= 0:
            raise ValueError("Quantity and price must be positive.")

        # Conservative fill-price approximation.
        fill_price = reference_price * (
            1 + SLIPPAGE_RATE if side == "BUY"
            else 1 - SLIPPAGE_RATE
        )

        notional = quantity * fill_price
        fee = notional * FEE_RATE

        if notional > MAX_ORDER_USD:
            return self._reject(
                side, quantity, reference_price, fill_price,
                fee, "Order exceeds USD notional limit"
            )

        if side == "BUY":
            if self.btc + quantity > MAX_POSITION_BTC:
                return self._reject(
                    side, quantity, reference_price, fill_price,
                    fee, "Maximum BTC position exceeded"
                )

            if notional + fee > self.cash:
                return self._reject(
                    side, quantity, reference_price, fill_price,
                    fee, "Insufficient simulated cash"
                )

            self.cash -= notional + fee
            self.btc += quantity

        else:
            if quantity > self.btc:
                return self._reject(
                    side, quantity, reference_price, fill_price,
                    fee, "Cannot sell more BTC than held"
                )

            self.cash += notional - fee
            self.btc -= quantity

        return self._record(
            side, quantity, reference_price, fill_price,
            fee, "FILLED", "Paper fill"
        )

    def _reject(self, side, qty, ref_price, fill_price, fee, reason):
        return self._record(
            side, qty, ref_price, fill_price, fee,
            "REJECTED", reason
        )

    def _record(self, side, qty, ref_price, fill_price, fee,
                status, reason):
        order_id = str(uuid.uuid4())

        self.db.execute("""
            INSERT INTO paper_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, "BTCUSDT", side, qty, ref_price,
            fill_price, fee, status, reason
        ))
        self.db.commit()

        result = {
            "order_id": order_id,
            "side": side,
            "quantity": qty,
            "fill_price": round(fill_price, 2),
            "fee": round(fee, 4),
            "status": status,
            "reason": reason,
            "cash": round(self.cash, 2),
            "btc": round(self.btc, 8),
        }
        print(result)
        return result

    def close(self):
        self.db.close()


if __name__ == "__main__":
    # Explicit local simulation; never submits an exchange order.
    broker = PaperBroker()
    try:
       broker.submit_market_order(
    side="BUY",
    quantity=0.0009,
    reference_price=100_000.00,
)
    finally:
        broker.close()
