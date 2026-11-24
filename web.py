"""Веб-сервер магазину: сайт, API замовлень і адмін-панель."""
import asyncio
import base64
import re
import time
from collections import defaultdict, deque

from aiohttp import web

import db
from config import (
    DELIVERY_PRICE,
    FREE_DELIVERY_FROM,
    PANEL_DIR,
    PANEL_PASSWORD,
    PAYMENT_METHODS,
    SITE_DIR,
    STATUSES,
    load_products,
)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{9,18}$")
GRINDS = {"beans", "filter", "espresso"}
_recent: dict[str, deque] = defaultdict(deque)


def _rate_limited(ip: str, limit: int = 5, window: int = 600) -> bool:
    now = time.monotonic()
    q = _recent[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def _authorized(request: web.Request) -> bool:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except Exception:
        return False
    return user == "admin" and password == PANEL_PASSWORD


@web.middleware
async def auth_middleware(request: web.Request, handler):
    public = not (request.path.startswith("/admin") or request.path.startswith("/api/admin"))
    if not public and not _authorized(request):
        return web.Response(status=401, text="Потрібна авторизація",
                            headers={"WWW-Authenticate": 'Basic realm="ROAST admin"'})
    return await handler(request)


def calculate(cart: list, products: dict) -> tuple[list[dict], int, int]:
    """Перераховує кошик за цінами з каталогу. Ціни від клієнта ігноруються."""
    items = []
    for row in cart[:30]:
        product = products.get(str(row.get("id")))
        qty = row.get("qty")
        grind = row.get("grind", "beans")
        if not product or not isinstance(qty, int) or not 1 <= qty <= 20 or grind not in GRINDS:
            raise ValueError("Некоректний товар у кошику")
        items.append({"id": product["id"], "name": product["name"], "price": product["price"],
                      "qty": qty, "grind": grind})
    if not items:
        raise ValueError("Кошик порожній")
    subtotal = sum(i["price"] * i["qty"] for i in items)
    delivery = 0 if subtotal >= FREE_DELIVERY_FROM else DELIVERY_PRICE
    return items, subtotal, delivery


async def api_create_order(request: web.Request) -> web.Response:
    ip = request.headers.get("X-Forwarded-For", request.remote or "?").split(",")[0].strip()
    if _rate_limited(ip):
        return web.json_response({"ok": False, "error": "Забагато замовлень. Спробуйте пізніше."}, status=429)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Некоректний запит"}, status=400)
    if data.get("website"):  # honeypot
        return web.json_response({"ok": True, "id": 0})

    c = data.get("customer") or {}
    customer = {k: str(c.get(k, "")).strip()[:120] for k in ("name", "phone", "city", "branch", "payment", "comment")}
    errors = {}
    if len(customer["name"]) < 2:
        errors["name"] = "Вкажіть ім'я"
    if not PHONE_RE.match(customer["phone"]):
        errors["phone"] = "Вкажіть коректний номер"
    if len(customer["city"]) < 2:
        errors["city"] = "Вкажіть місто"
    if not customer["branch"]:
        errors["branch"] = "Вкажіть відділення"
    if customer["payment"] not in PAYMENT_METHODS:
        errors["payment"] = "Оберіть спосіб оплати"
    if errors:
        return web.json_response({"ok": False, "errors": errors}, status=422)

    try:
        items, subtotal, delivery = calculate(data.get("items") or [], load_products())
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=422)

    order = db.create_order(customer, items, subtotal, delivery)
    bot = request.app.get("bot")
    if bot is not None:
        from bot import notify_admin

        # Сповіщення у фоні: покупець не чекає, поки відповість Telegram
        task = asyncio.create_task(notify_admin(bot, order))
        request.app["bg_tasks"].add(task)
        task.add_done_callback(request.app["bg_tasks"].discard)
    return web.json_response({"ok": True, "id": order["id"], "total": order["total"]}, status=201)


async def api_admin_orders(request: web.Request) -> web.Response:
    status = request.query.get("status") or None
    if status and status not in STATUSES:
        return web.json_response({"error": "Невідомий статус"}, status=400)
    return web.json_response({"orders": db.list_orders(status), "stats": db.stats(), "statuses": STATUSES})


async def api_admin_status(request: web.Request) -> web.Response:
    data = await request.json()
    if data.get("status") not in STATUSES:
        return web.json_response({"error": "Невідомий статус"}, status=400)
    order = db.set_status(int(request.match_info["order_id"]), data["status"])
    if order is None:
        return web.json_response({"error": "Не знайдено"}, status=404)
    return web.json_response({"order": order})


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(SITE_DIR / "index.html")


async def panel(_: web.Request) -> web.FileResponse:
    return web.FileResponse(PANEL_DIR / "index.html")


def create_app(bot=None) -> web.Application:
    app = web.Application(middlewares=[auth_middleware])
    app["bg_tasks"] = set()
    if bot is not None:
        app["bot"] = bot
    app.router.add_get("/", index)
    app.router.add_get("/admin", panel)
    app.router.add_post("/api/orders", api_create_order)
    app.router.add_get("/api/admin/orders", api_admin_orders)
    app.router.add_post("/api/admin/orders/{order_id:\\d+}/status", api_admin_status)
    app.router.add_static("/assets/", SITE_DIR / "assets")
    app.router.add_static("/data/", SITE_DIR / "data")
    return app
