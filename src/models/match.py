from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class BettingMarket(BaseModel):
    name: str
    betfair_link: Optional[str] = None
    data: Dict[str, str or float] = {}

class MatchNotification(BaseModel):
    id: str
    home_team: str
    away_team: str
    excapper_link: str
    betfair_link: Optional[str] = None
    notified_market: Optional[str] = None
    match_data: Optional[Dict[str, List[Dict[str, str]]]] = {} # Extracted tables data
    ai_analysis: Optional[str] = None

class ExcapperLoginResult(BaseModel):
    success: bool
    message: str
