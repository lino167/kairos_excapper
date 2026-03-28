from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union

class BettingMarket(BaseModel):
    name: str
    betfair_link: Optional[str] = None
    data: Dict[str, Union[str, float]] = {}

class MatchNotification(BaseModel):
    id: str
    home_team: str
    away_team: str
    excapper_link: str
    betfair_link: Optional[str] = None
    notified_market: Optional[str] = None
    match_data: Optional[Dict[str, List[List[str]]]] = {} # Raw extracted tables (List of Lists)
    cleaned_data: Optional[Dict[str, List[Dict[str, Union[float, str]]]]] = {} # Numeric/Calculable data (List of Dicts)
    market_links: Optional[Dict[str, str]] = {} # Market Name -> Betfair Link
    ai_analysis: Optional[str] = None
    raw_data: Optional[str] = None # Dados brutos textuais extras (ex: Dropping-Odds)
    should_notify: bool = True     # Decisão da IA de enviar ou não
    rejection_reason: Optional[str] = None
    pre_score: Optional[str] = None
    pre_minute: Optional[str] = None
    post_score: Optional[str] = None
    post_minute: Optional[str] = None

class ExcapperLoginResult(BaseModel):
    success: bool
    message: str
