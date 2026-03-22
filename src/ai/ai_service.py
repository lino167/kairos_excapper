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
        
        # Use cleaned_data for a more structured prompt if available
        if match_notification.cleaned_data:
            for table_id, rows in match_notification.cleaned_data.items():
                data_text += f"\nTabela: {table_id}\n"
                for row in rows:
                    # Convert dict to a clean string format
                    row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                    data_text += f"- {row_str}\n"
        else:
            # Fallback to raw match_data
            for table_id, row_data in match_notification.match_data.items():
                data_text += f"\nTabela: {table_id}\n"
                for row in row_data:
                    data_text += " | ".join(row) + "\n"
                
        prompt = f"""
        Você é um analista especialista em mercados de apostas esportivas e Smart Money.
        Analise os dados extraídos do Excapper para a seguinte partida:
        
        Times: {match_notification.home_team} vs {match_notification.away_team}
        Mercado: {match_notification.notified_market}
        
        ### Guia de Colunas do Excapper:
        - Summ: Volume total de dinheiro correspondido nesta seleção (liquidez).
        - Change: Variação de volume recente. Ex: "27 / 1.21" significa que entraram 27€ (1.21% do total da seleção).
        - Odds: Cotação atual.
        - All: Volume total de dinheiro em TODO o mercado (todas as seleções somadas).
        - Percent money on market: Quanto do dinheiro total do mercado está nesta seleção.
        - Score: Placar no momento da atualização.
        - Time: Minuto do jogo.
        
        ### Dados da Partida:
        {data_text}
        
        ### Sua Tarefa:
        Forneça uma análise concisa e técnica:
        1. Identifique anomalias: Há entradas bruscas de volume em relação ao total (Smart Money)?
        2. Pressão do Mercado: O volume nesta seleção é dominante (comparar Summ vs All)? 
        3. Relação Score/Odds: O preço (Odd) está justo para o placar e tempo de jogo?
        
        ### Conclusão Obrigatória (Sugestão de Aposta):
        Ao final da sua análise, você DEVE fornecer um bloco estruturado exatamente assim:
        
        <b>SUGESTÃO:</b> [Back/Lay/Não Apostar] na seleção [Nome da Seleção]
        <b>MERCADO:</b> [Nome do Mercado]
        <b>ODD MÍNIMA:</b> [Cotação sugerida]
        <b>CONFIANÇA:</b> [1 a 10]
        <b>RESUMO:</b> [Uma frase curta justificando a entrada]
        
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
