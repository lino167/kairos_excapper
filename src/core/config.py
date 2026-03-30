import os
from dotenv import load_dotenv
import json

# Load environment variables from config/.env if it exists
load_dotenv(os.path.join(os.getcwd(), 'config', '.env'))

# Excapper Credentials
EXCAPPER_USER = os.getenv('EXCAPPER_USER', '')
EXCAPPER_PASS = os.getenv('EXCAPPER_PASS', '')

# Telegram Bot
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# AI Model API Keys (Fill as needed)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'gemini')

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://dkwdtvaysyhvchrazutz.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '') or os.getenv('api_key_supabase', '')

# Optional: Load Supabase from Trae MCP config if env missing
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        mcp_path = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Trae", "User", "mcp.json")
        if os.path.isfile(mcp_path):
            with open(mcp_path, "r", encoding="utf-8") as f:
                mcp_cfg = json.load(f)
            SUPABASE_URL = SUPABASE_URL or mcp_cfg.get("SUPABASE_URL", SUPABASE_URL)
            SUPABASE_KEY = SUPABASE_KEY or mcp_cfg.get("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY)
except Exception:
    pass

# Application Settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
BROWSER_HEADLESS = os.getenv('BROWSER_HEADLESS', 'True').lower() == 'true'
CHECK_INTERVAL_SECONDS = int(os.getenv('CHECK_INTERVAL_SECONDS', '300')) # Default: 5 minutes

# Notification message for unauthenticated table
AUTH_REQUIRED_MESSAGE = "Login to the site to set up games in your favorites"
NO_NOTIFICATIONS_MESSAGE = "Configure the settings to add games to your notification or nothing was found by your parameters"

# Test mode: send rejected analyses to Telegram
SEND_REJECTED_TO_TELEGRAM = os.getenv('SEND_REJECTED_TO_TELEGRAM', 'False').lower() == 'true'
