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

        ### 📋 ESTRATÉGIAS DE ANÁLISE (O BOT SÓ APROVA SE ENCAIXAR EM UMA DELAS):

        #### PROTOCOLO 1: MONEY WAY (Liderança e Liquidez)
        - **Volume**: "Summ" > 6000€.
        - **Concentração**: "Percent money on market" > 75%.
        - **Janela de Odd**: Entre 1.50 e 4.50.
        - **Drop**: Queda superior a 15% em relação à Odd Inicial (> 2.00).

        #### PROTOCOLO 2: SHARP BETS (Explosão de Momentum)
        - **Pico de 1 Min**: "Change %" superior a 80% (Entrada massiva repentina).
        - **Valor da Odd**: Odds atuais superiores a 4.50 (Sharps pegando valor alto).
        - **Variação**: Queda superior a 10% da odd inicial.
        - **Status**: O jogo deve estar obrigatoriamente em "Live".
        - **Volume Mínimo**: "Summ" > 100€ (mesmo com volume baixo, o % de subida deve ser enorme).

        ### 🛡️ FILTRO DE SEGURANÇA (OBRIGATÓRIO):
        - Se o Drop/Pico foi causado APENAS por um cartão vermelho (`[RED_CARD]`) ou gol (`[GOAL/PENALTY]`), responda ENVIAR SINAL: NÃO.
        - O sinal deve ser fruto de movimentação estratégica de mercado, não apenas reação ao placar.

        ### Guia de Colunas do Excapper:
        - Summ: Dinheiro correspondido NESSA seleção específica (Gatilho: > 6000€).
        - Change: Dinheiro novo que entrou AGORA em Summ (Ex: 200€ / 3.3%).
        - Odds: Cotação atual no momento (Faixa: 1.50 a 4.50).
        - All: Volume total somando todas as seleções do mercado.
        - Percent money on market: Quanto do "All" está concentrado no "Summ" atual (Gatilho: > 75%).
        - Score: Placar no momento (Ex: 2-0).
        - Time: Minuto da partida.
        - Internal_Events: Alertas de Cartão Vermelho ou Gols detectados.

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
        <b>📝 FEELING:</b> [Uma frase curta justificando a entrada]

        IMPORTANTE: NÃO use markdown (nada de asteriscos).
        Use EXCLUSIVAMENTE a tag HTML <b> para negrito.
        """
        return prompt

    async def analyze_match(self, match_notification: MatchNotification):
        logging.info(f"Analisando partida com {self.provider}...")
        prompt = self.generate_analysis_prompt(match_notification)

        try:
            content = ""
            if self.provider == "gemini" and GEMINI_API_KEY:
                response = self.model.generate_content(prompt)
                if response.candidates and any(c.content.parts for c in response.candidates):
                    content = response.text
                else:
                    content = "[ENVIAR: NÃO] Análise bloqueada por política de conteúdo."
            elif self.provider == "openai" and OPENAI_API_KEY:
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000
                )
                content = response.choices[0].message.content

            # --- Lógica de Filtro e Registro de Predição ---
            import re

            # Extract Prediction (Ex: 🔥 INDICAÇÃO: Over 2.5)
            prediction = "N/A"
            match_pred = re.search(r'🔥 INDICAÇÃO:</b>\s*(.*)', content) or re.search(r'🔥 INDICAÇÃO:</b>\s*(.*)', content.replace('<b>', '<b>'))
            if not match_pred:
                # Fallback search if tag style varies
                match_pred = re.search(r'INDICAÇÃO: (.*)', content, re.IGNORECASE)

            if match_pred:
                prediction = match_pred.group(1).strip()

            if "SIM" in content or "Aprovado" in content or ("<b>🔥 INDICAÇÃO:</b>" in content and "furada" not in content.lower()):
                match_notification.should_notify = True
                match_notification.ai_analysis = content.strip()
                # Store prediction for DB
                match_notification.raw_data = prediction # Using raw_data as temp carrier for prediction
            else:
                match_notification.should_notify = False
                match_notification.ai_analysis = content.strip()
                # Reason for rejection (heurística)
                reason = "Critérios de aprovação não atendidos"
                if "furada" in content.lower():
                    reason = "Análise indicou 'furada'"
                elif "NÃO" in content or "rejeitado" in content.lower():
                    reason = "Resposta negativa explícita"
                match_notification.rejection_reason = reason

        except Exception as e:
            logging.error(f"Erro na análise: {e}")
            match_notification.should_notify = False
            match_notification.ai_analysis = f"Erro na análise: {e}"
            match_notification.rejection_reason = "Erro na análise"

        return match_notification
