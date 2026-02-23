from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class NewsResponse(BaseModel):
    id: int
    ticker: str          # DB 컬럼: ticker
    title: str           # DB 컬럼: title
    summary: str         # DB 컬럼: summary
    sentiment: str       # DB 컬럼: sentiment (positive/negative)
    impact_socre: int    # DB 컬럼: impact_l... (숫자니까 int)
    published_at: datetime # DB 컬럼: published_at
    company_name: Optional[str] = None

    class Config:
        from_attributes = True