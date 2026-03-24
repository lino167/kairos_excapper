import asyncio
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from src.models.match import MatchNotification

class DroppingOddsScraper:
    def __init__(self, headless=True):
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

    async def extract_market_tables(self, game_id):
        """Extrai as tabelas de odds de diferentes mercados para um jogo específico."""
        markets = {
            '1X2': f"https://dropping-odds.com/event.php?id={game_id}&t=1x2",
            'Total': f"https://dropping-odds.com/event.php?id={game_id}&t=total",
            'Handicap': f"https://dropping-odds.com/event.php?id={game_id}&t=handicap",
            'HT_Total': f"https://dropping-odds.com/event.php?id={game_id}&t=total_ht",
            'HT_1X2': f"https://dropping-odds.com/event.php?id={game_id}&t=1x2_ht"
        }
        
        extracted_data = {}
        
        for market_name, url in markets.items():
            try:
                logging.info(f"Extraindo tabela do mercado {market_name}...")
                await self.page.goto(url)
                await self.page.wait_for_timeout(1500)
                
                # A tabela de interesse é a que contém os dados de odds
                # Geralmente é a única tabela principal no corpo
                table = await self.page.query_selector('table')
                if table:
                    # Capturamos o texto formatado para a IA
                    text = await table.inner_text()
                    extracted_data[market_name] = text
                else:
                    extracted_data[market_name] = "Tabela não encontrada."
            except Exception as e:
                logging.error(f"Erro ao extrair mercado {market_name}: {e}")
                extracted_data[market_name] = f"Erro na extração: {e}"
                
        return extracted_data

    async def check_drops(self):
        logging.info("Checking for live drops on Dropping-Odds...")
        try:
            await self.page.goto(self.url)
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(3000)

            # Find all match rows on the live page
            rows = await self.page.query_selector_all('tbody tr.a_link')
            if not rows:
                logging.info("No live matches found.")
                return []

            matches_to_process = []
            for row in rows:
                game_id = await row.get_attribute('game_id')
                if not game_id:
                    continue

                cells = await row.query_selector_all('td')
                
                # Check for drop (just to include in the metadata, but we won't skip anymore)
                row_classes = await row.get_attribute('class') or ""
                has_drop = False
                drop_text = "Live"
                
                if any(r in row_classes for r in ['red1', 'red2', 'red3']):
                    has_drop = True
                    drop_text = "Drop (TR)"
                
                if not has_drop:
                    for cell in cells:
                        classes = await cell.get_attribute('class') or ""
                        color = await cell.evaluate('el => window.getComputedStyle(el).backgroundColor')
                        if any(r in classes for r in ['red1', 'red2', 'red3']):
                            has_drop = True
                            drop_text = await cell.inner_text()
                            break
                        import re
                        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', color)
                        if match and int(match.group(1)) > 180:
                            has_drop = True
                            drop_text = await cell.inner_text()
                            break

                home_team = await cells[2].inner_text() if len(cells) > 2 else "Unknown"
                away_team = await cells[4].inner_text() if len(cells) > 4 else "Unknown"

                # Agora coletamos TODOS os jogos para verificar o Excapper lá dentro
                matches_to_process.append({
                    'game_id': game_id,
                    'home': home_team.strip(),
                    'away': away_team.strip(),
                    'market': drop_text.strip(),
                    'has_active_drop': has_drop
                })

            logging.info(f"Encontrados {len(matches_to_process)} jogos live para verificar detalhes...")
            
            final_matches = []
            for item in matches_to_process:
                logging.info(f"Verificando detalhes de: {item['home']} vs {item['away']} (ID: {item['game_id']})")
                
                # 4. Verificar se tem link do Excapper (entramos em cada um!)
                try:
                    await self.page.goto(f"https://dropping-odds.com/event.php?id={item['game_id']}")
                    await self.page.wait_for_timeout(1500)
                    
                    excapper_link_el = await self.page.query_selector('a[href*="excapper.com"]')
                    if not excapper_link_el:
                        # logging.info(f"Skip: Sem link Excapper.")
                        continue
                    
                    excapper_link = await excapper_link_el.get_attribute('href')
                    exc_id = excapper_link.split('=')[-1]
                    
                    logging.info(f"✨ Link Excapper encontrado! Extraindo tabelas de mercado...")
                    
                    # 5. Extraímos as tabelas do Dropping-Odds
                    extra_tables = await self.extract_market_tables(item['game_id'])
                    
                    match_notif = MatchNotification(
                        id=exc_id,
                        home_team=item['home'],
                        away_team=item['away'],
                        excapper_link=excapper_link,
                        notified_market=f"Live (Drop: {item['has_active_drop']})"
                    )
                    
                    match_notif.raw_data = f"--- DADOS DO DROPPING-ODDS ---\n"
                    for m_name, m_text in extra_tables.items():
                        match_notif.raw_data += f"\n Mercado {m_name}:\n{m_text}\n"
                    
                    final_matches.append(match_notif)
                except Exception as e:
                    logging.error(f"Erro ao acessar {item['home']}: {e}")
                    continue
            
            # Voltar para a home no final do ciclo
            await self.page.goto(self.url)
            logging.info(f"Ciclo finalizado. Encontrados {len(final_matches)} jogos qualificados.")
            return final_matches
        except Exception as e:
            logging.error(f"Error checking live dropping-odds: {e}")
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
