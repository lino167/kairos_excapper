import logging
import google.generativeai as genai
from openai import OpenAI
from src.core.config import GEMINI_API_KEY, OPENAI_API_KEY
from src.models.match import MatchNotification

class AIService:
    def __init__(self, provider="openai"):
        self.provider = provider
        if provider == "gemini" and GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            # Relax safety settings for betting analysis
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            # Use a more stable and powerful model (pro-latest)
            self.model = genai.GenerativeModel('gemini-pro-latest', safety_settings=safety_settings)
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
        Analise os seguintes dados de apostas para uma partida de futebol:
        Times: {match_notification.home_team} vs {match_notification.away_team}
        Mercado Notificado: {match_notification.notified_market}
        Dados Extraídos da Partida:
        {data_text}
        
        Forneça uma análise concisa e técnica focando em:
        1.  Existem discrepâncias significativas no mercado ou movimentos de "Smart Money"?
        2.  O mercado notificado é uma boa oportunidade de aposta?
        3.  Qual é a estratégia de aposta recomendada para esta partida?
        
        IMPORTANTE: NÃO use markdown (nada de asteriscos). 
        Se você precisar destacar algo em negrito, use EXCLUSIVAMENTE a tag HTML: <b>texto desejado</b>.
        """
        return prompt

    async def analyze_match(self, match_notification: MatchNotification):
        logging.info(f"Analyzing match with {self.provider}...")
        prompt = self.generate_analysis_prompt(match_notification)
        
        try:
            if self.provider == "gemini" and GEMINI_API_KEY:
                response = self.model.generate_content(prompt)
                
                # Check if the response contains valid text to avoid 
                # "quick accessor requires valid Part" error
                if response.candidates and any(c.content.parts for c in response.candidates):
                    match_notification.ai_analysis = response.text
                else:
                    match_notification.ai_analysis = "A análise da IA foi bloqueada ou não retornou dados (possivelmente por política de conteúdo). Verifique os dados da partida."
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
