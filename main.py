import asyncio
import logging
from src.core.config import LOG_LEVEL, CHECK_INTERVAL_SECONDS, AI_PROVIDER, BROWSER_HEADLESS
from src.scrapers.excapper_scraper import ExcapperScraper
from src.scrapers.dropping_odds_scraper import DroppingOddsScraper
from src.ai.ai_service import AIService
from src.notifiers.telegram_notifier import TelegramNotifier
from src.models.match import MatchNotification

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class KairosExcapperBot:
    def __init__(self):
        self.excapper_scraper = None
        self.dropping_odds_scraper = None
        self.ai = AIService(provider=AI_PROVIDER) # Dynamic provider from config
        self.telegram = TelegramNotifier()
        self.notified_matches = set() # Store notified match IDs

    async def initialize(self):
        # Inicializa o Scraper do Excapper (apenas para extração direta, sem login obrigatório agora)
        self.excapper_scraper = await ExcapperScraper(headless=BROWSER_HEADLESS).init_browser()
            
        # Inicializa o Scraper do Dropping Odds
        self.dropping_odds_scraper = await DroppingOddsScraper(headless=BROWSER_HEADLESS).init_browser()
        return True

    async def run(self):
        if not await self.initialize():
            return

        while True:
            try:
                # Check Dropping-Odds Drops (Exclusive source now)
                logging.info("\n--- DROPPING-ODDS SCAN STARTING ---")
                dropping_matches = await self.dropping_odds_scraper.check_drops()
                await self.process_matches(dropping_matches)

                logging.info(f"Full cycle completed. Waiting {CHECK_INTERVAL_SECONDS} seconds...")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                
            except Exception as e:
                logging.error(f"System error in main loop: {e}")
                await asyncio.sleep(60) # Retry after 1 minute

    async def process_matches(self, matches):
        """Unified processing for matches from any source."""
        for match_notif in matches:
            if match_notif.id in self.notified_matches:
                logging.info(f"Skipping already notified match: {match_notif.home_team}")
                continue
                
            # 1. Extract Details from Excapper (since both provide Excapper links)
            try:
                detailed_notif = await self.excapper_scraper.extract_match_details(match_notif)
                logging.info(f"Extracted details for {match_notif.home_team}")
                
                # 2. AI Analysis
                detailed_notif = await self.ai.analyze_match(detailed_notif)
                logging.info("AI Analysis completed.")
                
                # 3. Final Filter: Only notify if AI says "SIM"
                ai_res = detailed_notif.ai_analysis.upper()
                send_signal = False
                if "ENVIAR SINAL:" in ai_res:
                    decision_part = ai_res.split("ENVIAR SINAL:")[1]
                    if "SIM" in decision_part and "NÃO" not in decision_part[:10]: # Check if SIM is the primary answer
                        send_signal = True
                
                if send_signal:
                    await self.telegram.send_match_alert(detailed_notif)
                    logging.info(f"Notification sent (AI Approved) for {match_notif.home_team}")
                else:
                    logging.info(f"Signal REJECTED by AI for {match_notif.home_team}. Skipping notification.")
                    
                self.notified_matches.add(match_notif.id)
            except Exception as e:
                logging.error(f"Error processing match {match_notif.id}: {e}")

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
