import logging
from supabase import create_client, Client
from src.core.config import SUPABASE_URL, SUPABASE_KEY
from src.models.match import MatchNotification

class DatabaseService:
    def __init__(self):
        self.supabase: Client = None
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                logging.info("Connected to Supabase.")
            except Exception as e:
                logging.error(f"Failed to connect to Supabase: {e}")
        else:
            logging.warning("Supabase URL or Key missing in configuration.")

    def save_match(self, match: MatchNotification):
        """Saves or updates a match in the kairos_matches table."""
        if not self.supabase:
            return

        data = {
            "id": match.id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "excapper_link": match.excapper_link,
            "dropping_odds_id": match.id, # Often same as match id in this logic
            "status": "pending",
            "should_notify": match.should_notify,
            "ai_analysis": match.ai_analysis
        }

        try:
            # Use upsert to handle existing matches
            self.supabase.table("kairos_matches").upsert(data).execute()
            logging.info(f"Match {match.home_team} vs {match.away_team} saved to DB.")
        except Exception as e:
            logging.error(f"Error saving match to DB: {e}")

    def save_market_data(self, match_id, market_name, source, data):
        """Saves market-specific data (rows/text) to the kairos_market_data table."""
        if not self.supabase:
            return

        payload = {
            "match_id": match_id,
            "market_name": market_name,
            "source": source,
            "data": data
        }

        try:
            self.supabase.table("kairos_market_data").insert(payload).execute()
        except Exception as e:
            logging.error(f"Error saving market data for {match_id}: {e}")

    def update_analysis(self, match_id, analysis, should_notify, prediction=None):
        """Updates the AI analysis and notification status for a match."""
        if not self.supabase:
            return

        data = {
            "ai_analysis": analysis,
            "should_notify": should_notify,
            "prediction": prediction
        }

        try:
            self.supabase.table("kairos_matches").update(data).eq("id", match_id).execute()
            logging.info(f"AI analysis updated for match ID: {match_id}")
        except Exception as e:
            logging.error(f"Error updating AI analysis for {match_id}: {e}")

    def get_matches_for_verification(self):
        """Retrieves matches that were notified and need result verification."""
        if not self.supabase:
            return []

        try:
            # Matches that were notified and don't have a final score yet
            response = self.supabase.table("kairos_matches")\
                .select("*")\
                .eq("should_notify", True)\
                .is_("final_score", "NULL")\
                .execute()
            return response.data
        except Exception as e:
            logging.error(f"Error fetching matches for verification: {e}")
            return []

    def save_final_result(self, match_id, final_score, final_data, was_correct=None):
        """Updates the match with final result and verification timestamp."""
        if not self.supabase:
            return

        data = {
            "final_score": final_score,
            "final_data": final_data,
            "was_correct": was_correct,
            "status": "completed",
            "verified_at": "now()"
        }

        try:
            self.supabase.table("kairos_matches").update(data).eq("id", match_id).execute()
            logging.info(f"Final result saved for match ID: {match_id}")
        except Exception as e:
            logging.error(f"Error saving final result for {match_id}: {e}")
