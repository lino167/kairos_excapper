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
            # Fallback para match_data bruto do Excapper
            for table_id, row_data in match_notification.match_data.items():
                data_text += f"\nTabela: {table_id}\n"
                for row in row_data:
                    data_text += " | ".join(row) + "\n"
                
        # Incluir tabelas específicas do Dropping-Odds se disponíveis
        if match_notification.raw_data:
            data_text += f"\n### DADOS ADICIONAIS DO MONITOR DE DROPS (Dropping-Odds):\n{match_notification.raw_data}\n"
            
        prompt = f"""
        Você é um apostador profissional com anos de estrada, daqueles que conhece cada movimento do mercado e tem um estilo direto, descolado e sem enrolação.
        Analise os seguintes dados de mercado para a partida:
        
        PARTIDA: {match_notification.home_team} vs {match_notification.away_team}
        SITUAÇÃO: {match_notification.notified_market}
        
        ### Guia Técnico (Para seu entendimento):
        - Summ: Volume total (liquidez).
        - Change: Grana que entrou agora. Ex: "2000 / 13%" é volume novo.
        - Odds: Cotação do momento.
        - Score/Time: Placar e minuto.
        
        ### Dados Coletados:
        {data_text}
        
        ### Sua Missão:
        Dê o seu veredito como quem está no grupo de elite dos apostadores. Use gírias do meio (derretendo, forra, entrada de valor, unidade, liquidez, back/lay) mas mantenha a autoridade. 
        
        REGRAS CRÍTICAS:
        1. NÃO mencione nomes de sites ou ferramentas (nada de falar "dados do Excapper" ou "Dropping-Odds").
        2. Fale como se você estivesse vendo o mercado agora.
        3. Seja direto. Se o cenário for ruim, diga que é "furada". Se for bom, diga que a "odd tá de valor".
        
        ### 🚨 FORMATO DO ALERTA (Obrigatório):
        Sua resposta deve ser curta e matadora, seguindo este modelo exato:
        
        <b>📊 VISÃO DO ESPECIALISTA:</b>
        [Um parágrafo curto e 'pro' sobre o movimento. Ex: "A odd tá derretendo no final e entrou um volume pesado que indica o gol. O mercado tá nervoso!"]
        
        <b>🔥 INDICAÇÃO:</b> [Back/Lay/Over] [Seleção]
        <b>⚽ MERCADO:</b> [Nome do Mercado]
        <b>💰 ODD MÍNIMA:</b> [Cotação sugerida]
        <b>⭐ CONFIANÇA:</b> [1 a 10]
        <b>📝 FEELING:</b> [Uma frase curta justificando a entrada com base no seu feeling de especialista]
        
        <b>✅ ENVIAR SINAL:</b> [SIM/NÃO]
        (Só responda SIM se o cenário for realmente lucrativo. Se for arriscado ou sem liquidez, mande um NÃO)
        
        IMPORTANTE: NÃO use markdown (nada de asteriscos). 
        Use EXCLUSIVAMENTE a tag HTML <b> para negrito.
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
