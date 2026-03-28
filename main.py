import asyncio
import logging
import os
from src.core.config import LOG_LEVEL, CHECK_INTERVAL_SECONDS, AI_PROVIDER, BROWSER_HEADLESS
from src.core.config import SEND_REJECTED_TO_TELEGRAM
from src.scrapers.excapper_scraper import ExcapperScraper
from src.scrapers.dropping_odds_scraper import DroppingOddsScraper
from src.ai.ai_service import AIService
from src.notifiers.telegram_notifier import TelegramNotifier
from src.models.match import MatchNotification
from src.core.database_service import DatabaseService

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class KairosExcapperBot:
    def __init__(self):
        self.excapper_scraper = None
        self.dropping_odds_scraper = None
        self.ai = AIService(provider=AI_PROVIDER)
        self.telegram = TelegramNotifier()
        self.db = DatabaseService()
        self.processed_game_ids = set() # To avoid redundant processing in a single cycle

    async def initialize(self):
        self.excapper_scraper = await ExcapperScraper(headless=BROWSER_HEADLESS).init_browser()
        self.dropping_odds_scraper = await DroppingOddsScraper(headless=BROWSER_HEADLESS).init_browser()
        return True

    async def run(self):
        if not await self.initialize():
            logging.error("Initialization failed. Exiting.")
            return

        while True:
            try:
                logging.info("\n🚀 --- STARTING NEW SCAN CYCLE ---")

                # 1. Get live games from Dropping-Odds list
                live_games = await self.dropping_odds_scraper.get_live_matches()
                logging.info(f"Found {len(live_games)} live matches on Dropping-Odds.")

                for game in live_games:
                    # 2. Process game: Search each market for drops & check events (Red/Penalty)
                    match_notif = await self.dropping_odds_scraper.process_game(
                        game['id'], game['home'], game['away'], self.excapper_scraper
                    )

                    if not match_notif:
                        continue # Skipped (No Excapper, Red Card, or Penalty)

                    logging.info(f"✅ Game {game['home']} vs {game['away']} passed Dropping-Odds filters.")

                    # 3. Save Match and Dropping-Odds data to DB
                    self.db.save_match(match_notif)
                    if "dropping_odds" in match_notif.match_data:
                        for m_name, m_data in match_notif.match_data["dropping_odds"].items():
                            self.db.save_market_data(match_notif.id, m_name, "dropping_odds", {"text": m_data})

                    # 4. Extract tables from Excapper
                    try:
                        match_notif = await self.excapper_scraper.extract_match_details(match_notif)
                        logging.info(f"✨ Extracted Excapper tables for {match_notif.home_team}")

                        # Save Excapper table data to DB
                        for tab_name, tab_rows in match_notif.match_data.items():
                            if tab_name != "dropping_odds": # Avoid re-saving
                                self.db.save_market_data(match_notif.id, tab_name, "excapper", {"rows": tab_rows})

                    except Exception as e:
                        logging.error(f"Error extracting Excapper details for {match_notif.home_team}: {e}")
                        continue

                    # 5. AI Analysis
                    try:
                        match_notif = await self.ai.analyze_match(match_notif)

                        self.db.update_analysis(
                            match_id=match_notif.id,
                            analysis=match_notif.ai_analysis,
                            should_notify=match_notif.should_notify,
                            prediction=match_notif.raw_data # Stored here by AIService
                        )

                        # 6. Telegram Alert if AI approves
                        if match_notif.should_notify:
                            await self.telegram.send_match_alert(match_notif)
                            logging.info(f"🔔 Notification SENT for {match_notif.home_team}")
                        else:
                            logging.info(f"❌ AI Rejected Signal for {match_notif.home_team}: {match_notif.rejection_reason}")
                            if SEND_REJECTED_TO_TELEGRAM:
                                reason = match_notif.rejection_reason or "Critérios de aprovação não atendidos"
                                prefix = f"<b>[TESTE] IA REJEITOU:</b> {reason}\n"
                                match_notif.ai_analysis = prefix + (match_notif.ai_analysis or "")
                                await self.telegram.send_match_alert(match_notif)
                                logging.info(f"🔔 Test notification SENT (rejected) for {match_notif.home_team}")

                    except Exception as e:
                        logging.error(f"AI Analysis Error: {e}")

                logging.info(f"--- Cycle completed. Waiting {CHECK_INTERVAL_SECONDS} seconds ---")

                # --- NEW: Check for matches that need result verification ---
                await self.verify_past_matches()

                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

            except Exception as e:
                logging.error(f"System error in main loop: {e}")
                await asyncio.sleep(60)

    async def verify_past_matches(self):
        """Checks past notified matches to extract final data and results."""
        logging.info("🔎 Checking for matches to verify results...")
        pending_verification = self.db.get_matches_for_verification()

        if not pending_verification:
            logging.info("No matches pending verification.")
            return

        for match_data in pending_verification:
            match_id = match_data['id']
            logging.info(f"⌛ Verifying result for match: {match_data['home_team']} (ID: {match_id})")

            try:
                # Create a temporary MatchNotification object
                stored_notif = MatchNotification(
                    id=match_id,
                    home_team=match_data['home_team'],
                    away_team=match_data['away_team'],
                    excapper_link=match_data['excapper_link']
                )

                # 1. Re-extract full data from Excapper (post-match)
                verified_notif = await self.excapper_scraper.extract_match_details(stored_notif)

                # 2. Extract final score/result (Best effort from tables)
                final_score = "Unknown"
                # Look for 'FT' or 'Final' or latest score in match_data tables
                for table_id, rows in verified_notif.match_data.items():
                    # Usually score is in the latter rows
                    if rows and len(rows) > 1:
                        # Simple heuristic: last row of a table often has the final state
                        last_row_text = " ".join(rows[-1])
                        if "-" in last_row_text:
                            final_score = rows[-1][1] if len(rows[-1]) > 1 else last_row_text

                logging.info(f"🏁 Final score detected for {match_data['home_team']}: {final_score}")

                # 3. Save everything to DB for training/AI review
                self.db.save_final_result(
                    match_id=match_id,
                    final_score=final_score,
                    final_data=verified_notif.match_data,
                    was_correct=None # IA will determine this later or we can add logic
                )

            except Exception as e:
                logging.error(f"Error verifying match {match_id}: {e}")

    async def close(self):
        if self.excapper_scraper:
            await self.excapper_scraper.close()
        if self.dropping_odds_scraper:
            await self.dropping_odds_scraper.close()

if __name__ == "__main__":
    bot = KairosExcapperBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("System shutting down...")
        asyncio.run(bot.close())
