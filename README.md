# 🦅 Kairos Excapper Bot

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/playwright-ready-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Kairos Excapper** is a professional, modular web scraping and AI-driven analysis tool for [Excapper.com](https://www.excapper.com/). It automates match monitoring, leverages AI for deep betting market analysis, and delivers real-time smart money alerts directly to Telegram.

---

## 🌟 Features

- **🔄 Automated Workflow**: Full automation from login to notification delivery.
- **🕵️ Professional Scraper**: Handles dynamic content and anti-bot measures using Playwright.
- **📊 Deep Data Mining**: Extracts all match-specific tables and betting market data.
- **🧠 AI Match Analysis**: Integrated with **OpenAI (GPT-4o)** and **Google Gemini** for expert-level market discrepancy analysis.
- **📲 Live Telegram Alerts**: Real-time delivery of match details, AI insights, and direct links to Excapper and Betfair.
- **🏗️ Modular Architecture**: Cleanly separated concerns for easy maintenance and scaling.

---

## 📂 Project Structure

```text
kairos_excapper/
├── config/             # Environment configuration and secrets
├── src/                # Primary source code
│   ├── ai/             # AI Analysis Logic (Gemini/OpenAI)
│   ├── core/           # Configuration, Logging, and Base Utilities
│   ├── flows/          # Business logic and main execution flow
│   ├── models/         # Pydantic structured data models
│   ├── notifiers/      # Telegram integration service
│   └── scrapers/       # Site-specific scraping logic (Excapper)
├── tests/              # Unit and integration tests
├── main.py             # Application entry point
├── requirements.txt    # Project dependencies
└── README.md           # Project documentation
```

---

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher.
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather)).
- API Keys for OpenAI or Google Gemini.

### Setup Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/lino167/kairos_excapper.git
   cd kairos_excapper
   ```

2. **Create a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

---

## ⚙️ Configuration

1. **Environment Variables**:
   Copy the example environment file:
   ```bash
   cp config/.env.example config/.env
   ```
2. **Setup Secrets**:
   Open `config/.env` and fill in your credentials:
   - `EXCAPPER_USER` / `EXCAPPER_PASS`: Your Excapper account details.
   - `TELEGRAM_TOKEN`: Your bot token.
   - `TELEGRAM_CHAT_ID`: Your chat or group ID.
   - `OPENAI_API_KEY` or `GEMINI_API_KEY`: Your AI provider keys.

---

## 🚀 Usage

To start the bot in production mode:
```bash
python main.py
```

### Advanced Settings
You can modify the check intervals and log levels in `src/core/config.py` or directly in the `.env` file.

---

## ⚠️ Disclaimer

This tool is for **educational and research purposes only**. Betting involves financial risk. Always gamble responsibly. The developers are not responsible for any financial losses incurred through the use of this software.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

**Built with ❤️ for the betting community.**
