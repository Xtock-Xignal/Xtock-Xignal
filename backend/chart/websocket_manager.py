import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Set

import yfinance as yf
from fastapi import WebSocket


def normalize_market_time(value) -> str:
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()

    if isinstance(value, str):
        stripped = value.strip()
        try:
            numeric_value = float(stripped)
        except ValueError:
            return stripped

        timestamp = numeric_value / 1000 if numeric_value > 1e12 else numeric_value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()

    return datetime.now(timezone.utc).astimezone().isoformat()


class SymbolHub:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.clients: Set[WebSocket] = set()
        self.stream_task: Optional[asyncio.Task] = None
        self.last_price: Optional[float] = None
        self.last_time: Optional[str] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.add(websocket)

        if self.last_price is not None:
            row = self.to_chart_row(self.last_price, self.last_time)
            await websocket.send_json({
                "type": "tick",
                "symbol": self.symbol,
                "price": self.last_price,
                "time": self.last_time,
                "row": row,
            })
        else:
            # 첫 연결 시 스트림 틱을 기다리지 않고 현재 가격을 즉시 전송
            asyncio.create_task(self._send_initial_snapshot(websocket))

        if self.stream_task is None or self.stream_task.done():
            self.stream_task = asyncio.create_task(self.run_stream())

    async def _send_initial_snapshot(self, websocket: WebSocket):
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, lambda: yf.Ticker(self.symbol))
            fi = await loop.run_in_executor(None, lambda: ticker.fast_info)
            price = getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None)
            if not price or float(price) <= 0:
                return
            price = float(price)
            now = datetime.now(timezone.utc).astimezone().isoformat()
            row = self.to_chart_row(price, now)
            await websocket.send_json({
                "type": "tick",
                "symbol": self.symbol,
                "price": price,
                "time": now,
                "row": row,
                "source": "snapshot",
            })
            if self.last_price is None:
                self.last_price = price
                self.last_time = now
        except Exception:
            pass

    def disconnect(self, websocket: WebSocket):
        self.clients.discard(websocket)

    async def broadcast(self, payload: dict):
        dead_clients = []

        for ws in self.clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead_clients.append(ws)

        for ws in dead_clients:
            self.clients.discard(ws)

    async def run_stream(self):
        """
        Yahoo Finance 실시간 WebSocket 스트림 사용
        """
        try:
            async with yf.AsyncWebSocket(verbose=False) as ws:
                await ws.subscribe(self.symbol)

                async def handle_message(message):
                    parsed = self.parse_message(message)
                    if not parsed:
                        return

                    self.last_price = parsed["price"]
                    self.last_time = parsed["time"]

                    await self.broadcast({
                        "type": "tick",
                        "symbol": self.symbol,
                        "price": self.last_price,
                        "time": self.last_time,
                        "row": self.to_chart_row(self.last_price, self.last_time),
                        "source": "yfinance_stream",
                    })

                # listen()은 message_handler를 받아 실시간 메시지를 처리
                await ws.listen(message_handler=handle_message)

        except Exception as e:
            # 스트림 실패 시 에러 전송
            await self.broadcast({
                "type": "error",
                "symbol": self.symbol,
                "message": str(e),
            })

    def parse_message(self, message) -> Optional[dict]:
        """
        Yahoo/yfinance 메시지는 종목과 필드 구성이 조금 다를 수 있어서
        가격/시간 필드를 방어적으로 추출
        """
        if not isinstance(message, dict):
            return None

        price = (
            message.get("price")
            or message.get("regularMarketPrice")
            or message.get("lastPrice")
            or message.get("last_price")
            or message.get("p")
        )

        if price is None:
            return None

        ts = message.get("time") or message.get("timestamp") or message.get("t")

        time_iso = normalize_market_time(ts)

        return {
            "price": float(price),
            "time": time_iso,
        }

    def to_chart_row(self, price: float, time_iso: Optional[str]) -> dict:
        """
        Return the same OHLC row shape as /api/chart/history rows so clients can
        merge live ticks into chart data without handling a separate format.
        """
        normalized_time = normalize_market_time(time_iso)
        date = normalized_time[:10]
        value = float(price)
        return {
            "date": date,
            "time": normalized_time,
            "open": value,
            "high": value,
            "low": value,
            "close": value,
            "volume": 0,
        }


symbol_hubs: Dict[str, SymbolHub] = {}


def get_hub(symbol: str) -> SymbolHub:
    symbol = symbol.upper()
    if symbol not in symbol_hubs:
        symbol_hubs[symbol] = SymbolHub(symbol)
    return symbol_hubs[symbol]
