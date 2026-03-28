import os
from dotenv import load_dotenv

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

# Application Settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
BROWSER_HEADLESS = os.getenv('BROWSER_HEADLESS', 'True').lower() == 'true'
CHECK_INTERVAL_SECONDS = int(os.getenv('CHECK_INTERVAL_SECONDS', '300')) # Default: 5 minutes

# Notification message for unauthenticated table
AUTH_REQUIRED_MESSAGE = "Login to the site to set up games in your favorites"
NO_NOTIFICATIONS_MESSAGE = "Configure the settings to add games to your notification or nothing was found by your parameters"
