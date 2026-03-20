import asyncio
import logging
from src.core.config import LOG_LEVEL, CHECK_INTERVAL_SECONDS, AI_PROVIDER
from src.scrapers.excapper_scraper import ExcapperScraper
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
        self.scraper = None
        self.ai = AIService(provider=AI_PROVIDER) # Dynamic provider from config
        self.telegram = TelegramNotifier()
        self.notified_matches = set() # Store notified match IDs

    async def initialize(self):
        self.scraper = await ExcapperScraper(headless=True).init_browser()
        login_res = await self.scraper.login()
        if not login_res.success:
            logging.error(f"Failed to login: {login_res.message}")
            return False
        return True

    async def run(self):
        if not await self.initialize():
            return

        while True:
            try:
                logging.info("\n--- NEW SCAN STARTING ---")
                notifications = await self.scraper.check_notifications()
                
                for match_notif in notifications:
                    if match_notif.id in self.notified_matches:
                        logging.info(f"Skipping already notified match: {match_notif.home_team}")
                        continue
                        
                    # 1. Extract Details
                    detailed_notif = await self.scraper.extract_match_details(match_notif)
                    logging.info(f"Extracted details for {match_notif.home_team}")
                    
                    # 2. AI Analysis
                    detailed_notif = await self.ai.analyze_match(detailed_notif)
                    logging.info("AI Analysis completed.")
                    
                    # 3. Notify Telegram
                    await self.telegram.send_match_alert(detailed_notif)
                    self.notified_matches.add(match_notif.id)
                    logging.info(f"Notification sent for {match_notif.home_team}")

                logging.info(f"Scan completed. Waiting {CHECK_INTERVAL_SECONDS} seconds...")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                
            except Exception as e:
                logging.error(f"System error in main loop: {e}")
                await asyncio.sleep(60) # Retry after 1 minute

    async def close(self):
        if self.scraper:
            await self.scraper.close()

if __name__ == "__main__":
    bot = KairosExcapperBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("System shutting down...")
        asyncio.run(bot.close())
