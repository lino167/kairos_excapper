import logging
from supabase import create_client, Client
from src.core.config import SUPABASE_URL, SUPABASE_KEY

class DatabaseService:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            logging.error("Supabase URL or Key not found in environment.")
            self.supabase = None
        else:
            self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    def save_match(self, match_notif):
        """Insert or update a match in the database."""
        if not self.supabase: return
        
        data = {
            "id": match_notif.id,
            "home_team": match_notif.home_team,
            "away_team": match_notif.away_team,
            "excapper_link": match_notif.excapper_link,
            "dropping_odds_id": getattr(match_notif, 'dropping_odds_id', None),
            "status": "pending"
        }
        try:
            return self.supabase.table("kairos_matches").upsert(data).execute()
        except Exception as e:
            logging.error(f"Error saving match to DB: {e}")

    def save_market_data(self, match_id: str, market_name: str, source: str, data: dict):
        """Insert market-specific data log."""
        if not self.supabase: return
        
        payload = {
            "match_id": match_id,
            "market_name": market_name,
            "source": source,
            "data": data
        }
        try:
            return self.supabase.table("kairos_market_data").insert(payload).execute()
        except Exception as e:
            logging.error(f"Error saving market data to DB: {e}")

    def update_analysis(self, match_id: str, analysis: str, should_notify: bool, prediction: str = None):
        """Update match record with AI insights."""
        if not self.supabase: return
        
        data = {
            "ai_analysis": analysis,
            "should_notify": should_notify,
            "prediction": prediction,
            "status": "notified" if should_notify else "rejected"
        }
        try:
            return self.supabase.table("kairos_matches").update(data).eq("id", match_id).execute()
        except Exception as e:
            logging.error(f"Error updating analysis in DB: {e}")

    def get_matches_for_verification(self):
        """Retrieve matches that were notified but don't have a final score yet."""
        if not self.supabase: return []
        
        try:
            res = self.supabase.table("kairos_matches") \
                .select("*") \
                .is_("final_score", "null") \
                .eq("status", "notified") \
                .execute()
            return res.data
        except Exception as e:
            logging.error(f"Error fetching matches for verification: {e}")
            return []

    def save_final_result(self, match_id: str, final_score: str, final_data: dict, was_correct: bool = None):
        """Finalize a match record with the result."""
        if not self.supabase: return
        
        data = {
            "final_score": final_score,
            "final_data": final_data,
            "was_correct": was_correct,
            "status": "verified",
            "verified_at": "now()" # Database handled
        }
        try:
            return self.supabase.table("kairos_matches").update(data).eq("id", match_id).execute()
        except Exception as e:
            logging.error(f"Error saving final result to DB: {e}")
