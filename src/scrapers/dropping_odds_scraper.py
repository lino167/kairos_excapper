import asyncio
import logging
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
        # Red Card: <img src="img/redcard.png">
        # Penalty: <img src="img/penalty.png">
        has_red_card = await self.page.query_selector('img[src*="redcard"]') is not None
        has_penalty = await self.page.query_selector('img[src*="penalty"]') is not None

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
            await self.page.wait_for_timeout(1000)

            excapper_link_el = await self.page.query_selector('a[href*="excapper.com"]')
            if not excapper_link_el:
                logging.info(f"⏭️ Skipping: No Excapper link found.")
                return None

            excapper_link = await excapper_link_el.get_attribute('href')
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
