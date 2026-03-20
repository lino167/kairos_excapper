import logging
from telegram import Bot
from src.core.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from src.models.match import MatchNotification

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
        self.chat_id = TELEGRAM_CHAT_ID

    async def send_match_alert(self, match_notification: MatchNotification):
        if not self.bot or not self.chat_id:
            logging.warning("Telegram Bot Token or Chat ID not configured.")
            return

        message = f"""
🚨 *NEW NOTIFICATION FOUND!* 🚨
⚽ *Match:* `{match_notification.home_team} vs {match_notification.away_team}`
📊 *Market:* `{match_notification.notified_market}`

🧠 *AI Analysis Insights:*
{match_notification.ai_analysis}

🔗 *Links:*
[Excapper Match Page]({match_notification.excapper_link})
[Betfair Market]({match_notification.betfair_link if match_notification.betfair_link else "N/A"})
        """
        
        try:
            logging.info(f"Sending Telegram alert for Match: {match_notification.home_team}")
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text=message, 
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")
