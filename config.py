"""Налаштування магазину. Значення беруться з файлу .env."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin")
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "8081"))
DB_PATH = BASE_DIR / os.getenv("DB_FILE", "shop.sqlite3")
SITE_DIR = BASE_DIR / "docs"
PANEL_DIR = BASE_DIR / "panel"
SHOP_NAME = os.getenv("SHOP_NAME", "ROAST Coffee")

FREE_DELIVERY_FROM = 1000  # грн — безкоштовна доставка від цієї суми
DELIVERY_PRICE = 80

STATUSES = {
    "new": "🆕 Нове",
    "confirmed": "📞 Підтверджено",
    "shipped": "📦 Відправлено",
    "done": "✅ Отримано",
    "cancelled": "❌ Скасовано",
}

PAYMENT_METHODS = {"card": "Карткою онлайн", "cod": "Накладений платіж"}


def load_products() -> dict:
    """Каталог — єдине джерело правди про ціни (і для сайту, і для сервера)."""
    with open(SITE_DIR / "data" / "products.json", encoding="utf-8") as f:
        return {p["id"]: p for p in json.load(f)}
