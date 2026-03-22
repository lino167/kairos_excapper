import logging
import html
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

        # Escape the AI analysis to avoid breaking HTML tags, but then allow <b> specifically
        analysis_escaped = html.escape(match_notification.ai_analysis)
        analysis_escaped = analysis_escaped.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')

        message = f"""
<b>🚨 NOVA NOTIFICAÇÃO ENCONTRADA! 🚨</b>

⚽ <b>Partida:</b> {match_notification.home_team} vs {match_notification.away_team}
📊 <b>Mercado:</b> {match_notification.notified_market}

🧠 <b>Insights da IA:</b>
{analysis_escaped}

🔗 <b>Links:</b>
<a href="{match_notification.excapper_link}">Página no Excapper</a>
<a href="{match_notification.betfair_link if match_notification.betfair_link else '#'}">Mercado Betfair</a>
        """
        
        # Telegram has a 4096 character limit. Truncate if necessary (safe limit 4000)
        if len(message) > 4090:
            message = message[:4000] + "\n\n<i>... [Texto truncado por limite de caracteres]</i>"

        try:
            logging.info(f"Sending Telegram alert for Match: {match_notification.home_team}")
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text=message, 
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")
