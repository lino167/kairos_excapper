import asyncio
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
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
        await Stealth().apply_stealth_async(self.page)
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
            await self.page.wait_for_selector('input[name="email"]', timeout=5000)
            
            # Fill credentials
            await self.page.fill('input[name="email"]', EXCAPPER_USER)
            await self.page.fill('input[name="psw"]', EXCAPPER_PASS)
                
            # Submit
            await self.page.click('input[type="submit"][value="Authorization"]')
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
        # Force navigation to the notification tab hash
        if not self.page.url.endswith("#fav"):
            await self.page.goto(f"{self.url}#fav")
            await self.page.wait_for_timeout(2000)
        
        # Ensure the 'Notification' tab is actually active/clicked
        # Sometimes goto #fav doesn't trigger the click handler if already on page
        await self.page.click('a.tab[href="#fav"]')
        await self.page.wait_for_timeout(3000)
        
        # Verify if the empty message is visible
        content = await self.page.content()
        if NO_NOTIFICATIONS_MESSAGE in content:
            logging.info("No active notifications found (matched empty message).")
            return []

        # Find match rows ONLY within the main table container to avoid sidebar/other rows
        # Based on subagent, the container is often #premach but let's be even more specific if possible
        # We look for tr[data-game-link] which is the standard for match rows on this site
        rows = await self.page.query_selector_all('#premach tr[data-game-link]')
        
        # If no rows found with data-game-link, it's definitely empty
        if not rows:
            logging.info("No match rows found in the table.")
            return []

        matches = []
        for row in rows:
            # Skip hidden rows if any
            if not await row.is_visible():
                continue
            game_link = await row.get_attribute('data-game-link')
            cols = await row.query_selector_all('td')
            if not game_link or len(cols) < 3:
                continue
                
            # Column indices: 0: Date, 1: Setting (Market), 2: Country, 3: League, 4: Teams
            cols_text = [await col.inner_text() for col in cols]
            if len(cols_text) < 5:
                continue
                
            market_notified = cols_text[1].strip()
            home_away = cols_text[4].strip()
            
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
