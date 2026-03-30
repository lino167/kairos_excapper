import asyncio
import logging
import math
import random
from typing import List, Dict, Any, Tuple
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from src.core.database_service import DatabaseService
from src.core.data_transformer import DataTransformer
from src.models.match import MatchNotification
from src.scrapers.excapper_scraper import ExcapperScraper
import asyncio

class HTCollector:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.url = "https://dropping-odds.com/betting_tools.php?view=drop_ht"
        self._playwright = None

    async def init(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        await Stealth().apply_stealth_async(self.page)
        return self

    async def close(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self._playwright:
                await self._playwright.stop()
        except:
            pass

    async def list_entries(self, limit: int = None) -> List[Dict[str, Any]]:
        await self.page.goto(self.url)
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)
        rows = await self.page.query_selector_all("tbody tr")
        results = []
        for row in rows:
            gid = await row.get_attribute("game_id")
            if not gid:
                link_el = await row.query_selector('a[href*="event.php?id="]')
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        try:
                            gid = href.split("id=")[-1].split("&")[0]
                        except:
                            pass
            if not gid:
                continue

            cells = await row.query_selector_all("td")
            home = ""
            away = ""
            final_score = None
            if cells and len(cells) >= 7:
                home = (await cells[2].inner_text()).strip()
                # Determine away team index (3 or 4)
                away_idx = 3
                away_text = (await cells[3].inner_text()).strip()
                if not away_text or away_text.lower() == "vs":
                    away_idx = 4
                    away_text = (await cells[4].inner_text()).strip()
                away = away_text
                
                # Final Score is usually in cells[6] if concluded
                try:
                    score_text = (await cells[6].inner_text()).strip()
                    if "-" in score_text and len(score_text) <= 10:
                        final_score = score_text
                except:
                    pass
            
            results.append({"game_id": gid, "home": home, "away": away, "href": f"event.php?id={gid}", "final_score": final_score})
            if limit and len(results) >= limit:
                break
        return results

    async def extract_market_tables(self, game_id: str) -> Dict[str, List[List[str]]]:
        markets = {
            "HT_Total": "total_ht",
            "HT_1X2": "1x2_ht",
            "Total": "total",
            "1X2": "1x2",
            "Handicap": "handicap",
        }
        tables: Dict[str, List[List[str]]] = {}
        for m_name, m_code in markets.items():
            url = f"https://dropping-odds.com/event.php?id={game_id}&t={m_code}"
            await self.page.goto(url)
            await self.page.wait_for_timeout(800)
            table = await self.page.query_selector("table")
            if not table:
                tables[m_name] = []
                continue
            head_cells = await table.query_selector_all("thead tr th")
            if not head_cells:
                head_cells = await table.query_selector_all("tr th")
            headers = []
            for h in head_cells:
                txt = (await h.inner_text()) or ""
                headers.append(txt.strip())
            body_rows = await table.query_selector_all("tbody tr")
            if not body_rows:
                body_rows = await table.query_selector_all("tr")
            rows_list: List[List[str]] = []
            if headers:
                rows_list.append(headers)
            for r in body_rows:
                tds = await r.query_selector_all("td")
                if not tds:
                    continue
                row_vals = []
                for td in tds:
                    row_vals.append(((await td.inner_text()) or "").strip())
                if row_vals:
                    rows_list.append(row_vals)
            tables[m_name] = rows_list
        return tables

    @staticmethod
    def _sanitize_excapper_link(href: str) -> str:
        href = href.strip()
        if href.startswith("`") and href.endswith("`"):
            href = href[1:-1].strip()
        href = href.replace("&amp;", "&")
        if href.startswith("http://excapper.com"):
            href = href.replace("http://", "https://", 1)
        return href

    @staticmethod
    def _is_valid_excapper_link(href: str) -> bool:
        import re as _re
        return bool(_re.fullmatch(r"https?://(www\.)?excapper\.com/\?action=game&id=\d+", href))

    async def find_excapper_link(self, game_id: str) -> str:
        import re as _re
        await self.page.goto(f"https://dropping-odds.com/event.php?id={game_id}")
        await self.page.wait_for_load_state("networkidle")
        try:
            await self.page.wait_for_selector('div.smenu', timeout=3000)
        except:
            pass
        el = await self.page.query_selector('div.smenu a:has-text("Excapper.com")')
        if not el:
            try:
                await self.page.wait_for_selector('a[href*="excapper.com"]', timeout=2000)
            except:
                pass
            el = await self.page.query_selector('a[href*="excapper.com"]')
        if el:
            raw = await el.get_attribute("href")
            href = self._sanitize_excapper_link(raw or "")
            return href if self._is_valid_excapper_link(href) else None
        html = await self.page.content()
        m = _re.search(r'https?://(?:www\.)?excapper\.com/\?action=game&id=\d+', html)
        if not m:
            return None
        href = self._sanitize_excapper_link(m.group(0))
        return href if self._is_valid_excapper_link(href) else None

class DatasetBuilder:
    def __init__(self, db: DatabaseService):
        self.db = db

    def fetch_training_records(self) -> List[Dict[str, Any]]:
        if not self.db.supabase:
            return []
        try:
            matches = self.db.supabase.table("kairos_matches").select("*").not_.is_("final_score", "null").execute().data
            ids = [m["id"] for m in matches if "id" in m]
            if not ids:
                return []
            market_data = self.db.supabase.table("kairos_market_data") \
                .select("*") \
                .in_("match_id", ids) \
                .eq("source", "dropping_odds") \
                .execute().data
            by_match: Dict[str, List[Dict[str, Any]]] = {}
            for md in market_data:
                mid = md.get("match_id")
                if not mid:
                    continue
                by_match.setdefault(mid, []).append(md)
            joined = []
            for m in matches:
                mid = m.get("id")
                if not mid or mid not in by_match:
                    continue
                joined.append({"match": m, "markets": by_match[mid]})
            return joined
        except Exception as e:
            logging.error(f"Erro ao montar registros de treino: {e}")
            return []

    @staticmethod
    def numeric_features_from_market(payload: Dict[str, Any]) -> Dict[str, float]:
        data = payload.get("data")
        if not isinstance(data, dict):
            return {}
        feats: Dict[str, float] = {}
        for k, v in data.items():
            if isinstance(v, (int, float)):
                feats[k] = float(v)
            elif isinstance(v, str):
                num = DataTransformer.clean_numeric_string(v)
                if isinstance(num, (int, float)):
                    feats[k] = float(num)
        return feats

    def build_xy(self) -> Tuple[List[List[float]], List[int], List[str]]:
        joined = self.fetch_training_records()
        X: List[List[float]] = []
        y: List[int] = []
        feature_keys: List[str] = []
        for rec in joined:
            mkts = rec["markets"]
            feats_acc: Dict[str, float] = {}
            for md in mkts:
                f = self.numeric_features_from_market(md)
                for k, v in f.items():
                    feats_acc[k] = v
            if not feats_acc:
                continue
            if not feature_keys:
                feature_keys = list(feats_acc.keys())
            vec = [feats_acc.get(k, 0.0) for k in feature_keys]
            label = 1 if bool(rec["match"].get("was_correct")) else 0
            X.append(vec)
            y.append(label)
        return X, y, feature_keys

class SimpleNN:
    def __init__(self, input_size: int, hidden_size: int = 8, lr: float = 0.01):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.lr = lr
        self.w1 = [[(random.random() - 0.5) * 0.1 for _ in range(input_size)] for _ in range(hidden_size)]
        self.b1 = [(random.random() - 0.5) * 0.1 for _ in range(hidden_size)]
        self.w2 = [(random.random() - 0.5) * 0.1 for _ in range(hidden_size)]
        self.b2 = (random.random() - 0.5) * 0.1

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x < -50:
            return 0.0
        if x > 50:
            return 1.0
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def _dsigmoid(s: float) -> float:
        return s * (s - 1.0) * -1.0

    @staticmethod
    def _relu(x: float) -> float:
        return x if x > 0 else 0.0

    @staticmethod
    def _drelu(x: float) -> float:
        return 1.0 if x > 0 else 0.0

    def forward(self, x: List[float]) -> Tuple[List[float], float]:
        h_pre = []
        for i in range(self.hidden_size):
            s = self.b1[i]
            wi = self.w1[i]
            for j in range(self.input_size):
                s += wi[j] * x[j]
            h_pre.append(s)
        h = [self._relu(v) for v in h_pre]
        o_pre = self.b2
        for i in range(self.hidden_size):
            o_pre += self.w2[i] * h[i]
        o = self._sigmoid(o_pre)
        return h, o

    def backward(self, x: List[float], h: List[float], o: float, y: int):
        error = o - y
        do = error * self._dsigmoid(o)
        for i in range(self.hidden_size):
            self.w2[i] -= self.lr * do * h[i]
        self.b2 -= self.lr * do
        dh = [self.w2[i] * do * self._drelu(h[i]) for i in range(self.hidden_size)]
        for i in range(self.hidden_size):
            for j in range(self.input_size):
                self.w1[i][j] -= self.lr * dh[i] * x[j]
            self.b1[i] -= self.lr * dh[i]

    def train(self, X: List[List[float]], y: List[int], epochs: int = 50):
        n = len(X)
        for _ in range(epochs):
            for i in range(n):
                h, o = self.forward(X[i])
                self.backward(X[i], h, o, y[i])

    def predict(self, x: List[float]) -> int:
        _, o = self.forward(x)
        return 1 if o >= 0.5 else 0

    def evaluate(self, X: List[List[float]], y: List[int]) -> float:
        if not X:
            return 0.0
        correct = 0
        for i in range(len(X)):
            p = self.predict(X[i])
            if p == y[i]:
                correct += 1
        return correct / len(X)

    def save_model(self, filepath: str, feature_keys: List[str]):
        import json
        data = {
            "w1": self.w1,
            "b1": self.b1,
            "w2": self.w2,
            "b2": self.b2,
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "lr": self.lr,
            "feature_keys": feature_keys
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)
        logging.info(f"Modelo salvo em {filepath}")

    @classmethod
    def load_model(cls, filepath: str):
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        model = cls(data["input_size"], data["hidden_size"], data["lr"])
        model.w1 = data["w1"]
        model.b1 = data["b1"]
        model.w2 = data["w2"]
        model.b2 = data["b2"]
        return model, data["feature_keys"]

async def collect_and_store(limit: int = None):
    db = DatabaseService()
    collector = await HTCollector(headless=True).init()
    exc_scraper = await ExcapperScraper(headless=True).init_browser()
    try:
        entries = await collector.list_entries(limit=limit)
        for e in entries:
            gid = e["game_id"]
            home = e["home"]
            away = e["away"]
            tables = await collector.extract_market_tables(gid)
            if not any(tables.values()):
                continue
            cleaned = {}
            for tname, rows in tables.items():
                cleaned[tname] = DataTransformer.transform_table_to_dicts(rows)
            exc_link = await collector.find_excapper_link(gid)
            match = MatchNotification(
                id=str(gid),
                home_team=home,
                away_team=away,
                excapper_link=exc_link,
                notified_market="Drop HT"
            )
            db.save_match(match)
            if e.get("final_score"):
                db.save_final_result(str(gid), e["final_score"], {}, was_correct=True) # Assuming correct if in list for now or just populating data
            
            for tname, rows in cleaned.items():
                if not rows:
                    continue
                db.save_market_data(str(gid), tname, "dropping_odds", {"rows": rows})
            if exc_link:
                try:
                    match = await exc_scraper.extract_match_details(match)
                    for tab_name, tab_rows in match.match_data.items():
                        if tab_rows and tab_name != "dropping_odds":
                            db.save_market_data(str(gid), tab_name, "excapper", {"rows": tab_rows})
                except Exception as _e:
                    logging.warning(f"Falha ao coletar dados do Excapper para jogo {gid}: {_e}")
    finally:
        try:
            await exc_scraper.close()
        except Exception:
            pass
        await collector.close()

def prepare_and_train(hidden: int = 8, lr: float = 0.01, epochs: int = 50):
    db = DatabaseService()
    builder = DatasetBuilder(db)
    X, y, feat_keys = builder.build_xy()
    if not X or not y:
        return {"status": "no_data", "features": feat_keys}
    model = SimpleNN(input_size=len(feat_keys), hidden_size=hidden, lr=lr)
    model.train(X, y, epochs=epochs)
    acc = model.evaluate(X, y)
    
    # NEW: Saves the model after training
    model.save_model("kairos_model.json", feat_keys)
    
    return {"status": "trained", "accuracy": acc, "features": feat_keys, "hidden": hidden, "lr": lr, "epochs": epochs, "saved_as": "kairos_model.json"}

def tune_hyperparams(hidden_opts: List[int], lr_opts: List[float], epochs: int = 50):
    db = DatabaseService()
    builder = DatasetBuilder(db)
    X, y, feat_keys = builder.build_xy()
    if not X or not y:
        return {"status": "no_data", "features": feat_keys}
    best = {"accuracy": -1.0}
    for h in hidden_opts:
        for lr in lr_opts:
            model = SimpleNN(input_size=len(feat_keys), hidden_size=h, lr=lr)
            model.train(X, y, epochs=epochs)
            acc = model.evaluate(X, y)
            if acc > best["accuracy"]:
                best = {"accuracy": acc, "hidden": h, "lr": lr, "epochs": epochs, "features": feat_keys}
    return {"status": "tuned", **best}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    asyncio.run(collect_and_store(limit=50))
    result = prepare_and_train(hidden=12, lr=0.02, epochs=100)
    print(result)
