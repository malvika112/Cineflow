"""SSE stream endpoint — production stock-sync path (see design doc 6.2).
Not wired to the patron frontend in v1, but fully functional: connect a
client to this and it will receive a stock_update event the instant any
checkout decrements stock."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.dependencies import get_event_bus

router = APIRouter(prefix="/api", tags=["realtime"])


@router.get("/stock/stream")
async def stock_stream(event_bus=Depends(get_event_bus)):
    return StreamingResponse(
        event_bus.subscribe("stock_updates"),
        media_type="text/event-stream",
    )
