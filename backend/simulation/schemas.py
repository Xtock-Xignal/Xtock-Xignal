from pydantic import BaseModel, Field
from typing import Optional, Literal


class CreateAccountRequest(BaseModel):
    nickname: str
    email: Optional[str] = None
    pin: str = Field(min_length=4, max_length=6)
    initial_cash: float = Field(default=10000000, gt=0)


class BuySellRequest(BaseModel):
    user_id: str
    symbol: str
    quantity: int = Field(gt=0)
    pin: str = Field(min_length=4, max_length=6)
    price: Optional[float] = Field(default=None, gt=0)


class AutoTradeRequest(BaseModel):
    user_id: str
    symbol: str
    type: Literal["BUY", "SELL"]
    target_price: float = Field(gt=0)
    quantity: int = Field(gt=0)
