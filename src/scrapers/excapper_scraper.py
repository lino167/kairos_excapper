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
        try:
            await self.page.goto(self.url)
            await self.page.wait_for_load_state("networkidle")
            
            # Check if already logged in
            await self.page.click('a.tab[href="#fav"]')
            await self.page.wait_for_timeout(3000)
            
            content = await self.page.content()
            if AUTH_REQUIRED_MESSAGE not in content:
                logging.info("Already logged in or login message not found.")
                return ExcapperLoginResult(success=True, message="Already logged in")

            # Click Sign in button
            await self.page.click('text="Sign in"')
            await self.page.wait_for_selector('input[name="email"]', timeout=5000)
            
            # Fill credentials
            await self.page.fill('input[name="email"]', EXCAPPER_USER)
            await self.page.fill('input[name="psw"]', EXCAPPER_PASS)
                
            # Submit
            await self.page.click('input[type="submit"][value="Authorization"]')
            
            # Wait for redirection and stabilizing
            await self.page.wait_for_load_state("load")
            await self.page.wait_for_timeout(5000)
            
            # Verify login by checking Notification tab again
            await self.page.click('a.tab[href="#fav"]')
            await self.page.wait_for_timeout(3000)
            
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
        
        # Ensure the 'Notification' tab is active
        await self.page.click('a.tab[href="#fav"]')
        await self.page.wait_for_timeout(3000)
        
        # Find match rows. In the #fav tab, data-game-link is on the <td>, not the <tr>.
        # We find all <tr> that contain a <td> with data-game-link.
        rows = await self.page.query_selector_all('#fav tr:has(td[data-game-link])')
        
        if not rows:
            logging.info("No notification rows found in the #fav table.")
            return []

        matches = []
        for row in rows:
            # Skip hidden rows
            if not await row.is_visible():
                continue
                
            cols = await row.query_selector_all('td')
            if len(cols) < 5:
                continue
            
            # Extract link from the FIRST cell that has it
            target_cell = await row.query_selector('td[data-game-link]')
            if not target_cell:
                continue
                
            game_link = await target_cell.get_attribute('data-game-link')
            cols_text = [await col.inner_text() for col in cols]
            
            # Expected Columns: 0: Date, 1: Setting, 2: Flag, 3: League, 4: Teams, 5: Market
            market_notified = cols_text[1].strip() if len(cols_text) > 1 else "Unknown"
            home_away = cols_text[4].strip() if len(cols_text) > 4 else "Unknown"
            
            teams = home_away.split(' - ')
            home_team = teams[0].strip() if len(teams) > 0 else "Unknown"
            away_team = teams[1].strip() if len(teams) > 1 else "Unknown"
            
            matches.append(MatchNotification(
                id=game_link.split('=')[-1],
                home_team=home_team,
                away_team=away_team,
                excapper_link=f"{self.url}{game_link}" if not game_link.startswith('http') else game_link,
                notified_market=market_notified
            ))
            
        logging.info(f"Found {len(matches)} active notifications.")
        return matches

    async def extract_match_details(self, match_notification: MatchNotification):
        logging.info(f"Extracting details for match: {match_notification.home_team} vs {match_notification.away_team}")
        await self.page.goto(match_notification.excapper_link)
        await self.page.wait_for_load_state("networkidle")
        
        # Extract Betfair link
        betfair_btn = await self.page.query_selector('a.btn[href*="betfair.com"]')
        if betfair_btn:
            match_notification.betfair_link = await betfair_btn.get_attribute('href')
            
        # Extract all relevant tables
        tables_data = {}
        tables = await self.page.query_selector_all('table')
        for idx, table in enumerate(tables):
            rows = await table.query_selector_all('tr')
            table_rows = []
            for row in rows:
                cols = await row.query_selector_all('td, th')
                row_data = [await col.inner_text() for col in cols]
                # Filter out empty or mostly empty rows
                if any(cell.strip() for cell in row_data):
                    table_rows.append(row_data)
                    
            # Only include tables that seem to have data (more than 1 row/column)
            if len(table_rows) > 1 and len(table_rows[0]) > 1:
                # Limit total rows per table to avoid hitting token limits
                tables_data[f"table_{idx}"] = table_rows[:50]
                
        match_notification.match_data = tables_data
        return match_notification

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
