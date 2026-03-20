import asyncio
import logging
from playwright.async_api import async_playwright
from playwright_stealth.stealth import stealth_async
from src.core.config import EXCAPPER_USER, EXCAPPER_PASS, AUTH_REQUIRED_MESSAGE, NO_NOTIFICATIONS_MESSAGE
from src.models.match import MatchNotification, ExcapperLoginResult

class ExcapperScraper:
    def __init__(self, headless=True):
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.url = "https://www.excapper.com/"

    async def init_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        await stealth_async(self.page)
        return self

    async def login(self):
        logging.info("Attempting to login to Excapper...")
        await self.page.goto(self.url)
        
        # Check if already logged in by looking for Notification tab message
        await self.page.click('a.tab[href="#fav"]')
        await self.page.wait_for_timeout(2000) # Give it a moment to load the table content
        
        content = await self.page.content()
        if AUTH_REQUIRED_MESSAGE not in content:
            logging.info("Already logged in or login message not found.")
            return ExcapperLoginResult(success=True, message="Already logged in")

        # Click Sign in button
        try:
            await self.page.click('text="Sign in"')
            await self.page.wait_for_selector('input.lightform', timeout=5000)
            
            # Fill credentials
            inputs = await self.page.query_selector_all('input.lightform')
            if len(inputs) >= 2:
                await inputs[0].fill(EXCAPPER_USER)
                await inputs[1].fill(EXCAPPER_PASS)
                
            # Submit
            await self.page.click('input.btn.btn-orange[value="Authorization"]')
            await self.page.wait_for_load_state("networkidle")
            
            # Verify login by checking Notification tab again
            await self.page.click('a.tab[href="#fav"]')
            await self.page.wait_for_timeout(2000)
            
            post_login_content = await self.page.content()
            if AUTH_REQUIRED_MESSAGE in post_login_content:
                logging.error("Login failed: Still seeing the login message.")
                return ExcapperLoginResult(success=False, message="Login verification failed")
            
            logging.info("Login successful.")
            return ExcapperLoginResult(success=True, message="Login successful")
        except Exception as e:
            logging.error(f"Login failed: {e}")
            return ExcapperLoginResult(success=False, message=str(e))

    async def check_notifications(self):
        logging.info("Checking for new notifications...")
        await self.page.click('a.tab[href="#fav"]')
        await self.page.wait_for_timeout(2000)
        
        # Check for NO_NOTIFICATIONS_MESSAGE or empty table
        content = await self.page.content()
        if NO_NOTIFICATIONS_MESSAGE in content:
            logging.info("No active notifications found.")
            return []

        # Find match rows
        rows = await self.page.query_selector_all('tr[data-game-link]')
        matches = []
        for row in rows:
            game_link = await row.get_attribute('data-game-link')
            cols = await row.query_selector_all('td')
            if not game_link or len(cols) < 3:
                continue
                
            # Basic info extraction from row (names, time, market)
            # You might need to refine the indexing based on the site structure
            home_away = await cols[1].inner_text()
            market_notified = await cols[2].inner_text() # Adjust column index
            
            teams = home_away.split(' - ')
            home_team = teams[0].strip() if len(teams) > 0 else "Unknown"
            away_team = teams[1].strip() if len(teams) > 1 else "Unknown"
            
            matches.append(MatchNotification(
                id=game_link.split('=')[-1],
                home_team=home_team,
                away_team=away_team,
                excapper_link=f"{self.url}{game_link}",
                notified_market=market_notified
            ))
            
        logging.info(f"Found {len(matches)} notifications.")
        return matches

    async def extract_match_details(self, match_notification: MatchNotification):
        logging.info(f"Extracting details for match: {match_notification.home_team} vs {match_notification.away_team}")
        await self.page.goto(match_notification.excapper_link)
        await self.page.wait_for_load_state("networkidle")
        
        # Extract Betfair link
        betfair_btn = await self.page.query_selector('a.btn[href*="betfair.com"]')
        if betfair_btn:
            match_notification.betfair_link = await betfair_btn.get_attribute('href')
            
        # Extract all tables
        tables_data = {}
        tables = await self.page.query_selector_all('table')
        for idx, table in enumerate(tables):
            rows = await table.query_selector_all('tr')
            table_rows = []
            for row in rows:
                cols = await row.query_selector_all('td, th')
                row_data = [await col.inner_text() for col in cols]
                if row_data:
                    table_rows.append(row_data)
            if table_rows:
                tables_data[f"table_{idx}"] = table_rows
                
        match_notification.match_data = tables_data
        return match_notification

    async def close(self):
        if self.browser:
            await self.browser.close()
