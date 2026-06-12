from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
from chart.service import get_chart_history_data
from chart.websocket_manager import get_hub

router = APIRouter(prefix="/api/chart", tags=["chart"])

@router.get("/history/{symbol}")
def get_chart_history(
    symbol: str,
    period: str = "1d",
    interval: str = "1m",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    return get_chart_history_data(symbol, period, interval, start_date, end_date)

@router.websocket("/ws/{symbol}")
async def chart_ws(websocket: WebSocket, symbol: str):
    hub = get_hub(symbol)
    try:
        await hub.connect(websocket)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)
