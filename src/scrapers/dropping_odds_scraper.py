import asyncio
import logging
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from src.models.match import MatchNotification

class DroppingOddsScraper:
    def __init__(self, headless=False):
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.url = "https://dropping-odds.com/index.php?view=live"

    async def init_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        await Stealth().apply_stealth_async(self.page)
        return self

    async def check_for_events(self):
        """Checks the current page for Red Card or Penalty icons."""
        counts = await self._get_event_counts()
        if counts is not None:
            has_red_card = counts.get("red_card_any", False)
            has_penalty = counts.get("penalty_any", False)
        else:
            has_red_card = await self._has_event_icon_in_tables("redcard")
            has_penalty = await self._has_event_icon_in_tables("penalty")

        if has_red_card:
            logging.warning("🚩 Red Card detected! Skipping match.")
            return True, "Red Card"
        if has_penalty:
            logging.warning("⚽ Penalty detected! Skipping match.")
            return True, "Penalty"

        return False, None

    async def get_live_matches(self):
        """Get the list of live matches from the main live page."""
        logging.info("Fetching live matches from Dropping-Odds...")
        try:
            await self.page.goto(self.url)
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(2000)

            rows = await self.page.query_selector_all('tbody tr.a_link')
            matches = []
            for row in rows:
                game_id = await row.get_attribute('game_id')
                if not game_id: continue
                cells = await row.query_selector_all('td')
                if len(cells) < 5: continue

                home = (await cells[2].inner_text()).strip()
                away = (await cells[4].inner_text()).strip()
                matches.append({'id': game_id, 'home': home, 'away': away})

            return matches
        except Exception as e:
            logging.error(f"Error fetching live matches: {e}")
            return []

    async def process_game(self, game_id, home, away):
        """Processes a single game: checks markets, events, and Excapper link."""
        logging.info(f"🔍 Processing game: {home} vs {away} (ID: {game_id})")

        # 1. First visit main event page to find Excapper link
        try:
            await self.page.goto(f"https://dropping-odds.com/event.php?id={game_id}")
            await self.page.wait_for_load_state("networkidle")
            try:
                await self.page.wait_for_selector('div.smenu', timeout=5000)
            except:
                pass

            excapper_link_el = await self.page.query_selector('div.smenu a:has-text("Excapper.com")')
            if not excapper_link_el:
                excapper_link_el = await self.page.query_selector('a[href*="excapper.com"]')
            if not excapper_link_el:
                logging.info(f"⏭️ Skipping: No Excapper link found.")
                return None

            excapper_link_raw = await excapper_link_el.get_attribute('href')
            excapper_link = self._sanitize_excapper_link(excapper_link_raw or "")
            if not self._is_valid_excapper_link(excapper_link):
                logging.info("⏭️ Skipping: Invalid Excapper link.")
                return None
            exc_id = excapper_link.split('=')[-1]

            # 2. Check for events on the main page first
            has_event, event_type = await self.check_for_events()
            if has_event:
                return None

            # 3. Visit and extract each market tab
            markets = {
                '1X2': '1x2',
                'Total': 'total',
                'Handicap': 'handicap',
                'HT_Total': 'total_ht',
                'HT_1X2': '1x2_ht'
            }

            extracted_tables = {}
            for m_name, m_code in markets.items():
                url = f"https://dropping-odds.com/event.php?id={game_id}&t={m_code}"
                await self.page.goto(url)
                await self.page.wait_for_timeout(1000)

                # Check for events in each market too
                has_event, _ = await self.check_for_events()
                if has_event:
                    return None

                table = await self.page.query_selector('table')
                if table:
                    # We store the table as HTML or clean text for the DB
                    extracted_tables[m_name] = await table.inner_text()
                else:
                    extracted_tables[m_name] = "Tabela não encontrada."

            # 4. Create MatchNotification object
            match_notif = MatchNotification(
                id=exc_id,
                home_team=home,
                away_team=away,
                excapper_link=excapper_link,
                notified_market="Live Drop Search"
            )
            match_notif.match_data = {"dropping_odds": extracted_tables}
            return match_notif

        except Exception as e:
            logging.error(f"Error processing game {game_id}: {e}")
            return None

    async def check_drops(self):
        """Deprecated: Use get_live_matches + process_game instead for the new flow."""
        return []

    async def close(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except:
            pass

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
        return bool(re.fullmatch(r"https?://(www\.)?excapper\.com/\?action=game&id=\d+", href))

    async def _has_event_icon_in_tables(self, icon: str) -> bool:
        selectors = [
            f"table tbody tr td img[src*='{icon}']",
            f"table tr td img[src*='{icon}']",
        ]
        for sel in selectors:
            try:
                elements = await self.page.query_selector_all(sel)
                for el in elements:
                    if await el.is_visible():
                        tr_class = await el.evaluate("el.closest('tr')?.className || ''")
                        if "legend" in tr_class or "header" in tr_class:
                            continue
                        return True
            except:
                continue
        return False

    @staticmethod
    def _parse_pair(text: str):
        m = re.search(r"(\\d+)\\s*-\\s*(\\d+)", text)
        if not m:
            return None
        try:
            return int(m.group(1)), int(m.group(2))
        except:
            return None

    async def _get_event_counts(self):
        tables = await self.page.query_selector_all("table")
        if not tables:
            return None
        red_labels = ["red", "red card", "red cards", "rc"]
        pen_labels = ["penalty", "penalties", "pen"]
        red_idx = None
        pen_idx = None
        found = False
        for table in tables:
            header_cells = await table.query_selector_all("thead tr th")
            if not header_cells:
                header_cells = await table.query_selector_all("tr th")
            headers = [((await h.inner_text()) or "").strip().lower() for h in header_cells]
            if headers:
                for i, h in enumerate(headers):
                    if red_idx is None and any(lbl in h for lbl in red_labels):
                        red_idx = i
                    if pen_idx is None and any(lbl in h for lbl in pen_labels):
                        pen_idx = i
                body_rows = await table.query_selector_all("tbody tr")
                if not body_rows:
                    body_rows = await table.query_selector_all("tr")
                red_any = False
                pen_any = False
                if red_idx is not None or pen_idx is not None:
                    for row in body_rows:
                        cells = await row.query_selector_all("td")
                        if not cells:
                            continue
                        if red_idx is not None and red_idx < len(cells):
                            txt = (await cells[red_idx].inner_text()) or ""
                            pair = self._parse_pair(txt)
                            if pair and (pair[0] > 0 or pair[1] > 0):
                                red_any = True
                        if pen_idx is not None and pen_idx < len(cells):
                            txt = (await cells[pen_idx].inner_text()) or ""
                            pair = self._parse_pair(txt)
                            if pair and (pair[0] > 0 or pair[1] > 0):
                                pen_any = True
                        if red_any or pen_any:
                            break
                    found = True
                    return {"red_card_any": red_any, "penalty_any": pen_any}
        if not found:
            return None
