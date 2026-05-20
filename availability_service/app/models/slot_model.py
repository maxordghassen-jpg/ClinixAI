from pydantic import BaseModel

from app.models.enums import SlotStatus


class SlotModel(BaseModel):
    start: str
    end: str
    status: SlotStatus = SlotStatus.AVAILABLE
