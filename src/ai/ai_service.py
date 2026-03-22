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
        - Change: Variação de volume recente. Ex: "2000 / 13%" significa que entraram 2000€ (13% da seleção).
        - Odds: Cotação atual.
        - All: Volume total no mercado inteiro.
        - Score: Placar no momento da atualização (Ex: 1-0).
        - Time: Minuto do jogo.
        
        ### Raciocínio Estratégico Exigido (Placar x Tempo):
        A IA deve correlacionar esses dados usando os seguintes padrões vencedores:
        1. **Late Drama (80'+)**: Entradas massivas de Change % (>10%) no final de jogos empatados ou com 1 gol de vantagem são sinais CRÍTICOS de um gol tardio.
        2. **Goleada/Pressão Contínua (20'-60')**: Entradas acima de 500€ em Over quando o favorito já vence por 2-0 antecipam goleadas (próximo gol).
        3. **Recuperação (Underdog/Empate)**: Se o favorito está empatando e o Change % dispara no 2º tempo, o mercado está prevendo o gol da vitória.
        4. **Cálculo de Valor**: Se o tempo restante é curto (<10 min) e a Odd está abaixo de 1.40, avalie se o risco compensa mesmo com Smart Money.
        
        ### Dados da Partida:
        {data_text}
        
        ### Sua Tarefa (Linguagem de Tipster Profissional):
        Assuma a postura de um Tipster Especialista em Live. Sua análise deve ser direta, vibrante e usar a linguagem dos apostadores (sem ser puramente técnica).
        1. Identifique o Movimento: Houve "Dinheiro Profissional" (Smart Money) entrando agora?
        2. Pressão em Campo: O volume injetado justifica o risco pelo tempo que falta? 
        3. Oportunidade de Green: O cenário é favorável para um gol ou manutenção do placar?
        
        ### 🚨 FORMATO DO SINAL (Obrigatório):
        Sua resposta FINAL deve ser curta e impactante, seguindo este modelo exato:
        
        <b>📊 ANALISE DO ESPECIALISTA:</b>
        [Um parágrafo curto e direto sobre o que o mercado está fazendo agora, usando termos como "derretimento de odd", "pressão no over", "volume dominante"]
        
        <b>🔥 INDICAÇÃO:</b> [Back/Lay/Over] [Seleção]
        <b>⚽ MERCADO:</b> [Nome do Mercado]
        <b>💰 ODD MÍNIMA:</b> [Cotação sugerida]
        <b>⭐ CONFIANÇA:</b> [1 a 10]
        <b>📝 RESUMO:</b> [Uma frase "matadora" justificando o sinal]
        
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
