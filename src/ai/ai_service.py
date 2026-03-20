import logging
import google.generative_ai as genai
from openai import OpenAI
from src.core.config import GEMINI_API_KEY, OPENAI_API_KEY
from src.models.match import MatchNotification

class AIService:
    def __init__(self, provider="openai"):
        self.provider = provider
        if provider == "gemini" and GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
        elif provider == "openai" and OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            logging.warning(f"No API key provided for AI provider: {provider}")

    def generate_analysis_prompt(self, match_notification: MatchNotification):
        """Build the prompt for match analysis."""
        data_text = ""
        for table_id, row_data in match_notification.match_data.items():
            data_text += f"\nTable: {table_id}\n"
            for row in row_data:
                data_text += " | ".join(row) + "\n"
                
        prompt = f"""
        Analyze the following betting data for a football match:
        Teams: {match_notification.home_team} vs {match_notification.away_team}
        Market (Notified): {match_notification.notified_market}
        Extracted Match Data:
        {data_text}
        
        Provide a concise analysis focusing on:
        1.  Are there any significant market discrepancies or smart money movements?
        2.  Is the notified market a good betting opportunity?
        3.  What is the recommended betting strategy for this match?
        
        Be specific and clinical in your analysis. Use technical betting terms if necessary.
        """
        return prompt

    async def analyze_match(self, match_notification: MatchNotification):
        logging.info(f"Analyzing match with {self.provider}...")
        prompt = self.generate_analysis_prompt(match_notification)
        
        try:
            if self.provider == "gemini" and GEMINI_API_KEY:
                # Synchronous call for now, could be wrapped in executor
                response = self.model.generate_content(prompt)
                match_notification.ai_analysis = response.text
            elif self.provider == "openai" and OPENAI_API_KEY:
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000
                )
                match_notification.ai_analysis = response.choices[0].message.content
            else:
                match_notification.ai_analysis = "AI Analysis unavailable (Check API keys)."
        except Exception as e:
            logging.error(f"AI analysis failed: {e}")
            match_notification.ai_analysis = f"Analysis error: {e}"
        
        return match_notification
