import logging
from typing import List, Dict, Any
from src.core.database_service import DatabaseService
from src.core.data_transformer import DataTransformer

class PatternSeeker:
    def __init__(self, db: DatabaseService):
        self.db = db

    def get_winning_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves historical matches that were profitable and extracts their core features.
        """
        if not self.db.supabase:
            return []
        
        try:
            # Seleciona partidas corretas que têm dados de mercado
            response = self.db.supabase.table("kairos_matches") \
                .select("id, home_team, away_team, final_score, was_correct, ai_analysis") \
                .eq("was_correct", True) \
                .not_.is_("final_score", "null") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            
            matches = response.data
            patterns = []

            for m in matches:
                mid = m["id"]
                # Busca as variações de mercado dessa partida
                mkt_resp = self.db.supabase.table("kairos_market_data") \
                    .select("*") \
                    .eq("match_id", mid) \
                    .execute()
                
                market_summary = {}
                for md in mkt_resp.data:
                    m_name = md["market_name"]
                    m_data = md["data"].get("rows", [])
                    if m_data:
                        # Pega o primeiro registro (geralmente o gatilho da aposta)
                        trigger_row = m_data[1] if len(m_data) > 1 else m_data[0]
                        market_summary[m_name] = trigger_row

                patterns.append({
                    "match_id": mid,
                    "teams": f"{m['home_team']} vs {m['away_team']}",
                    "result": m["final_score"],
                    "patterns": market_summary
                })
            
            return patterns
        except Exception as e:
            logging.error(f"Erro ao buscar padrões: {e}")
            return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = DatabaseService()
    seeker = PatternSeeker(db)
    winners = seeker.get_winning_patterns(3)
    for w in winners:
        print(f"--- Patrão de Vitória: {w['teams']} (Placar: {w['result']}) ---")
        for mkt, data in w['patterns'].items():
            print(f"Mercado: {mkt} -> Dados: {data}")
