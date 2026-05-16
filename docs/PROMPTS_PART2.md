# PROMPT PLAYBOOK — часть 2 (F03 → F12)

> Продолжение `PROMPT_PLAYBOOK.md`. Открывай после закрытия F02.

---

## Промпт №5 — F03 Webhook + точка входа

**Кому:** агенту
**Когда:** после закрытия F02

```markdown
F02 закрыта. Открываем фичу **F03 — Webhook + точка входа (FastAPI)**.

Шаг 1: Обнови feature_list.json — F03 в "in_progress".

Шаг 2: Создай файлы:

### src/bot/webhook.py

```python
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Request

logger = logging.getLogger(__name__)
router = APIRouter()

# Глобальная переменная для router'а handlers (заполняется в main.py при старте)
_update_processor = None


def set_update_processor(processor) -> None:
    """Регистрирует обработчик updates от MAX. Вызывается из main.py."""
    global _update_processor
    _update_processor = processor


@router.post("/webhook")
async def receive_update(request: Request, background: BackgroundTasks) -> dict[str, Any]:
    """MAX доставляет update сюда. Отвечаем 200 OK мгновенно, обработка — в фоне."""
    payload = await request.json()
    logger.info("webhook received update: %s", payload.get("update_type", "unknown"))

    if _update_processor is not None:
        background.add_task(_update_processor, payload)

    return {"ok": True}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

### src/main.py

```python
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.bot.max_client import MAXClient
from src.bot.webhook import router as webhook_router, set_update_processor
from src.config import get_settings

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def process_update(payload: dict) -> None:
    """Обработчик update. В F05+ будет роутить в handlers."""
    logger.info("processing update: type=%s", payload.get("update_type"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    set_update_processor(process_update)

    if settings.webhook_url:
        async with MAXClient() as client:
            ok = await client.subscribe_webhook(settings.webhook_url)
            if ok:
                logger.info("Webhook subscribed at %s", settings.webhook_url)
            else:
                logger.warning("Failed to subscribe webhook")

    yield

    logger.info("Shutting down...")


app = FastAPI(title="Astralaser MAX Bot v2", lifespan=lifespan)
app.include_router(webhook_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=get_settings().app_port)
```

### tests/test_webhook.py

```python
from fastapi.testclient import TestClient
from src.main import app


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_webhook_accepts_post():
    with TestClient(app) as c:
        r = c.post("/webhook", json={"update_type": "message", "message": {}})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
```

### Шаг 3: проверка локально

Подними бота:
```
python -m uvicorn src.main:app --reload --port 8000
```

В отдельном терминале:
```
curl http://localhost:8000/health
curl -X POST http://localhost:8000/webhook -H "Content-Type: application/json" -d "{}"
```

Оба должны вернуть 200.

### Шаг 4: проверка через ngrok (опционально, если есть)

Если у тебя есть ngrok:
```
ngrok http 8000
```
Скопируй HTTPS URL → пропиши в .env как WEBHOOK_URL.
Перезапусти бот — он должен сам зарегистрировать webhook через subscribe_webhook.
Напиши боту в MAX `/start` — в логах должно появиться `processing update`.

### Шаг 5: проверка тестами

```
python -m pytest -v
python -m ruff check .
python -m mypy src/
.\init.ps1
```

### Шаг 6: Session Record и стоп.

Запреты:
- НЕ пиши логику handlers — это F04.
- НЕ создавай router.py для роутинга updates → handlers — это F04.
- НЕ трогай models.py.
```

**После закрытия F03 — Промпт №6.**

---

## Промпт №6 — F04 Главное меню + политика конфиденциальности

**Кому:** агенту
**Когда:** после закрытия F03

```markdown
F03 закрыта. Открываем фичу **F04 — Главное меню + политика конфиденциальности**.

Шаг 1: Обнови feature_list.json — F04 в "in_progress".

Шаг 2: Создай файлы:

### src/bot/router.py

Главный роутер updates. Принимает payload от MAX, определяет тип (message / callback_query), извлекает chat_id, user_id, text/data, и вызывает handler.

```python
from __future__ import annotations
import logging
from typing import Any
from src.bot.max_client import MAXClient
from src.bot.handlers import start as start_handler

logger = logging.getLogger(__name__)


class UpdateRouter:
    def __init__(self, client: MAXClient):
        self.client = client

    async def process(self, payload: dict[str, Any]) -> None:
        try:
            update_type = payload.get("update_type", "")

            if update_type == "message_created":
                await self._handle_message(payload)
            elif update_type == "message_callback":
                await self._handle_callback(payload)
            else:
                logger.debug("ignored update type: %s", update_type)
        except Exception:
            logger.exception("error processing update")

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        msg = payload.get("message", {})
        chat_id = msg.get("recipient", {}).get("chat_id") or msg.get("chat_id")
        user = msg.get("sender", {})
        user_id = user.get("user_id") or user.get("id")
        text = msg.get("body", {}).get("text", "")

        if not chat_id or not user_id:
            return

        # Команды
        if text.startswith("/start"):
            await start_handler.handle_start(self.client, chat_id, user_id, user)
        # ...другие команды добавим в следующих фичах

    async def _handle_callback(self, payload: dict[str, Any]) -> None:
        cb = payload.get("callback", {})
        callback_id = cb.get("callback_id")
        chat_id = cb.get("message", {}).get("recipient", {}).get("chat_id")
        message_id = cb.get("message", {}).get("body", {}).get("mid")
        user_id = cb.get("user", {}).get("user_id")
        data = cb.get("payload", "")

        if not callback_id or not chat_id or not user_id:
            return

        # ACK callback (best-effort)
        await self.client.answer_callback_query(callback_id)

        # Маршрутизация
        if data == "consent:accept":
            await start_handler.handle_consent_accept(self.client, chat_id, user_id, message_id)
        elif data == "consent:decline":
            await start_handler.handle_consent_decline(self.client, chat_id, message_id)
        # ...другие callbacks в следующих фичах
```

### src/bot/keyboards.py

```python
"""Универсальные клавиатуры (inline и reply)."""

from typing import TypedDict


class InlineButton(TypedDict, total=False):
    text: str
    callback_data: str
    url: str


def main_menu_reply_keyboard() -> list[list[dict]]:
    """Главное меню (reply keyboard MAX). Если MAX не поддерживает reply — fallback на inline."""
    return [
        [{"text": "📚 Каталог", "callback_data": "catalog"}, {"text": "🛒 Корзина", "callback_data": "cart"}],
        [{"text": "📦 Мои заказы", "callback_data": "orders"}, {"text": "❓ Помощь", "callback_data": "help"}],
        [{"text": "💬 Менеджер", "callback_data": "contact"}],
    ]


def consent_keyboard() -> list[list[dict]]:
    return [
        [{"text": "✅ Принимаю", "callback_data": "consent:accept"}],
        [{"text": "❌ Отклонить", "callback_data": "consent:decline"}],
    ]
```

### src/services/user_service.py

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.crud import user as user_crud
from src.db.models import User


async def get_or_create_user(session: AsyncSession, max_user_id: str, **info) -> User:
    user = await user_crud.get_user_by_max_id(session, max_user_id)
    if user:
        return user
    return await user_crud.create_user(session, max_user_id=max_user_id, **info)


async def has_given_consent(session: AsyncSession, max_user_id: str) -> bool:
    user = await user_crud.get_user_by_max_id(session, max_user_id)
    return user is not None and user.consent_at is not None


async def record_consent(session: AsyncSession, max_user_id: str) -> None:
    await user_crud.update_consent(session, max_user_id)
```

### src/bot/handlers/start.py

```python
from datetime import datetime
from src.bot.max_client import MAXClient
from src.bot.keyboards import main_menu_reply_keyboard, consent_keyboard
from src.db.engine import async_session_maker
from src.services import user_service

PRIVACY_TEXT = """🔒 Перед тем как продолжить

Мы храним только данные, необходимые для обработки заказа: ваш ID в MAX, имя, телефон и адрес доставки.

Мы НЕ передаём данные третьим лицам. Вы можете удалить свои данные, написав менеджеру.

Подтверждая, вы соглашаетесь с обработкой персональных данных."""

MAIN_MENU_TEXT = """🌟 Astralaser — украшения с персональной гравировкой

Здесь вы можете заказать кулоны, браслеты и брелоки с индивидуальной гравировкой для себя или в подарок.

Мы поможем подобрать изделие, согласуем ваш текст и изготовим украшение специально под ваш заказ.

✨ Срок изготовления: 1–2 рабочих дня
📦 Доставка СДЭК по всей России
💝 Бархатная сумочка в комплекте

Выберите раздел, чтобы начать."""

MAIN_MENU_PHOTO = "https://i.postimg.cc/vm2rdtGg/IMG-20260505-105827.png"

DECLINE_TEXT = "Без согласия на обработку данных мы не можем продолжить.\nВы всегда можете вернуться, нажав /start."


async def handle_start(client: MAXClient, chat_id, user_id, user_info: dict) -> None:
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(
            session,
            max_user_id=str(user_id),
            username=user_info.get("username"),
            full_name=user_info.get("name") or user_info.get("first_name", ""),
        )
        await session.commit()
        has_consent = user.consent_at is not None

    if not has_consent:
        await client.send_message(chat_id, PRIVACY_TEXT, reply_markup=consent_keyboard())
    else:
        await client.send_message(
            chat_id, MAIN_MENU_TEXT,
            reply_markup=main_menu_reply_keyboard(),
            photo_url=MAIN_MENU_PHOTO,
        )


async def handle_consent_accept(client: MAXClient, chat_id, user_id, message_id) -> None:
    async with async_session_maker() as session:
        await user_service.record_consent(session, max_user_id=str(user_id))
        await session.commit()

    await client.edit_message(
        chat_id, message_id,
        MAIN_MENU_TEXT,
        reply_markup=main_menu_reply_keyboard(),
        photo_url=MAIN_MENU_PHOTO,
    )


async def handle_consent_decline(client: MAXClient, chat_id, message_id) -> None:
    await client.edit_message(chat_id, message_id, DECLINE_TEXT)
```

### Обнови src/main.py

В `process_update` подключи UpdateRouter:

```python
from src.bot.router import UpdateRouter

# Внутри lifespan создай глобально:
_router: UpdateRouter | None = None

async def process_update(payload: dict) -> None:
    if _router:
        await _router.process(payload)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _router
    settings = get_settings()
    client = MAXClient()
    _router = UpdateRouter(client)
    set_update_processor(process_update)
    if settings.webhook_url:
        await client.subscribe_webhook(settings.webhook_url)
    yield
    await client.close()
```

### tests/test_handlers.py

Минимум 5 тестов с RecordingClient (мок MAXClient, который запоминает вызовы):

1. `/start` для нового пользователя → отправляется политика
2. `/start` для пользователя с consent_at → отправляется главное меню
3. `consent:accept` → consent_at записан, edit_message с главным меню
4. `consent:decline` → edit_message с DECLINE_TEXT
5. Главное меню caption НЕ содержит URL (проверка чистоты)

### Шаг 3: проверка через ngrok

Подними бота, обнови WEBHOOK_URL в .env, отправь `/start` боту в MAX. Должна прийти политика. Нажми «Принимаю» — главное меню. Нажми «Отклонить» — текст отказа.

Сделай скриншот для прогресс-лога.

### Шаг 4: проверка тестами

Все стандартные команды зелёные.

### Шаг 5: Session Record и стоп.

Запреты:
- НЕ создавай catalog handler, cart handler — это следующие фичи.
- НЕ добавляй обработку других callback_data, кроме consent:* и базовых команд.
```

**После закрытия F04 — Промпт №7.**

---

## Промпт №7 — F05 Каталог: категории, карточки, пагинация фото

**Кому:** агенту
**Когда:** после F04

```markdown
F04 закрыта. Открываем фичу **F05 — Каталог: категории, карточки, пагинация фото**.

Шаг 1: Обнови feature_list.json — F05 в "in_progress".

Шаг 2: Создай:

### src/services/catalog_service.py

DTO + функции:

- `get_categories_with_count(session)` → list[CategoryDTO(id, title, slug, products_count)]
- `get_products_by_slug(session, slug)` → list[ProductDTO]
- `get_product_card(session, product_id, photo_index=0)` → ProductCardDTO(title, price, description, photo_url, photo_count, photo_index, category_slug)

DTO — frozen @dataclass.

### src/bot/handlers/catalog.py

Реализуй:

```python
async def show_catalog(client, chat_id, message_id):
    """Показывает категории. edit_message если message_id, иначе send."""

async def show_category(client, chat_id, message_id, slug):
    """Показывает товары категории. Если 1 товар — сразу карточку."""

async def show_product_card(client, chat_id, message_id, product_id, photo_index=0):
    """Карточка товара с пагинацией фото."""

async def add_to_cart(client, chat_id, user_id, message_id, product_id):
    """Добавить в корзину, edit_message с уведомлением."""
```

### Callback patterns (формат "type:arg1:arg2")

- `catalog` — показать список категорий
- `cat:{slug}` — открыть категорию
- `prod:{id}` — открыть карточку
- `photo:{id}:{idx}` — переключить фото
- `add:{id}` — в корзину
- `home` — главное меню

### Расширь src/bot/router.py

Добавь обработку всех новых callback patterns в `_handle_callback`. Используй регулярки или split(":") с проверкой длины.

### src/bot/keyboards.py — добавь:

- `catalog_categories_keyboard(categories)` — список категорий
- `category_products_keyboard(products, category_slug)` — список товаров в категории + Назад
- `product_card_keyboard(product_id, photo_index, photo_count, category_slug)` — пагинация + В корзину + Назад + Главная
- `added_to_cart_keyboard()` — Перейти в корзину / Назад к товару / Главная

### Тесты

- test_catalog.py: get_categories_with_count, get_product_card
- test_router.py: каждый callback pattern роутится в правильный handler

### Шаг 3: ручной тест в MAX

Пройди:
1. /start → главное меню
2. 📚 Каталог → видишь 3 категории
3. Колье и кулоны → 2 товара
4. Кулон-столбик → карточка с фото 1/6
5. ▶️ → фото 2/6, ▶️ ... → циклически
6. 🛒 В корзину → "Добавлено", кнопки
7. 🔙 К категории → возврат
8. 🏠 Главная → главное меню

Все экраны через edit_message — НЕ должно быть свалки сообщений.

Сделай скриншоты карточки и каталога для evidence.

### Шаг 4: проверка тестами + Session Record + стоп.

Запреты:
- НЕ реализуй корзину — это F06.
- НЕ реализуй оформление заказа — это F07.
- Кнопка [🛒 Корзина] в главном меню пока может вести в заглушку «скоро».
```

**После F05 — Промпт №8.**

---

## Промпт №8 — F06 Корзина

**Кому:** агенту
**Когда:** после F05

```markdown
F05 закрыта. Открываем **F06 — Корзина**.

Шаг 1: feature_list.json — F06 in_progress.

Шаг 2:

### src/services/cart_service.py

- `get_cart_view(session, user_id)` → CartViewDTO(items: list[CartItemDTO], total: int)
- `add_product(session, user_id, product_id)` → новый total
- `remove_product(session, user_id, product_id)`
- `change_quantity(session, user_id, product_id, delta: int)` — delta может быть -1 или +1; если итог 0 — удаляет
- `clear_cart(session, user_id)`

### src/bot/handlers/cart.py

```python
async def show_cart(client, chat_id, user_id, message_id):
    """Показать корзину или сообщение что пусто."""

async def change_quantity(client, chat_id, user_id, message_id, product_id, delta):
    ...

async def remove_item(client, chat_id, user_id, message_id, product_id):
    ...

async def clear_cart(client, chat_id, user_id, message_id):
    ...
```

### Callback patterns

- `cart` — показать корзину
- `qty:{product_id}:inc` / `qty:{product_id}:dec`
- `rm:{product_id}`
- `clear` → подтверждение
- `clear:yes` / `clear:no`

### Клавиатуры

- `cart_keyboard(items)` — для каждого товара ряд `[➖] [➕] [❌]`, внизу [✅ Оформить] [🗑 Очистить] [🏠 Главная]
- `empty_cart_keyboard()` — [📚 К каталогу] [🏠 Главная]

### Тесты

- test_cart.py: add, get, change_qty (inc/dec/zero→remove), clear, empty cart display

### Ручной тест в MAX

1. Добавь 2 товара в корзину
2. /cart → видишь оба, итог
3. Нажми ➕ — кол-во растёт, итог пересчитывается
4. ➖ до 0 — товар удаляется
5. ❌ — другой товар удаляется
6. 🗑 Очистить → подтверждение → пусто

Скриншот корзины с товарами.

### Шаг 3: проверка + Session Record + стоп.
```

**После F06 — Промпт №9.**

---

## Промпт №9 — F07 Оформление заказа (FSM)

**Кому:** агенту
**Когда:** после F06

```markdown
F06 закрыта. Открываем **F07 — Оформление заказа (FSM)**.

Шаг 1: feature_list.json — F07 in_progress.

Шаг 2:

### src/services/fsm_service.py

```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.crud import user_state as state_crud


async def get_state(session: AsyncSession, user_id: int) -> tuple[str | None, dict]:
    row = await state_crud.get_state(session, user_id)
    if not row:
        return None, {}
    return row.state, json.loads(row.data or "{}")


async def set_state(session: AsyncSession, user_id: int, state: str, data: dict) -> None:
    await state_crud.set_state(session, user_id, state, json.dumps(data, ensure_ascii=False))


async def clear_state(session: AsyncSession, user_id: int) -> None:
    await state_crud.clear_state(session, user_id)
```

### src/services/order_service.py

```python
async def place_order(session, user_id, name, phone, address, notes) -> Order:
    """Создать Order + OrderItems со snapshot. Очистить корзину."""

async def format_manager_notification(order: Order) -> str:
    """Текст уведомления менеджеру."""

async def format_user_confirmation(order: Order) -> str:
    """Текст подтверждения пользователю."""
```

### src/bot/handlers/order.py

States: `order:waiting_name`, `:waiting_phone`, `:waiting_address`, `:waiting_notes`

Реализация:
- При callback `checkout`:
  - проверь корзину не пуста
  - (F09 потом добавит проверку подписки)
  - set_state(`order:waiting_name`)
  - send_message «Шаг 1/4: Как вас зовут?» + кнопка [❌ Отмена]
- При получении сообщения, если state начинается с `order:waiting_*`:
  - валидируй
  - сохрани в data
  - переходи к следующему шагу
  - на `waiting_notes` после ввода: создай заказ, очисти state, очисти корзину, отправь подтверждение пользователю и уведомление обоим админам

### Валидация
- Имя: 2–100 символов, есть хотя бы 1 пробел или 2+ слова
- Телефон: regex `^\+?\d[\d\s\-\(\)]{9,17}$` (нормализуй пробелы)
- Адрес: 5–300 символов
- Заметки: 0–500 символов (можно пустую — заменить на «обсудим с менеджером»)

При невалидном вводе: «Не похоже на телефон. Формат: +7 XXX XXX XX XX. Попробуйте ещё раз».

### Callback patterns
- `checkout` — старт FSM
- `order:cancel` — отмена → clear_state → возврат в корзину

### Расширь router.py

В `_handle_message`: проверь, есть ли активный state у user. Если да — направь в order handler.

### Уведомления админам

Используй `settings.admin_ids_list` — отправь обоим:

```
🔔 Новый заказ #1234
👤 ...
📞 ...
📍 ...
[список товаров]
💰 Итого: ... ₽
✏️ Гравировка: ...
```

### Тесты

- test_order.py:
  - place_order создаёт Order + OrderItems со snapshot названий и цен
  - после place_order корзина пуста
  - FSM проходит 4 шага и создаёт заказ
  - Невалидный телефон → state не меняется
  - cancel → state очищен

### Ручной тест

1. Добавь товар в корзину
2. ✅ Оформить заказ → шаг 1/4
3. Введи имя → шаг 2/4
4. Перезапусти бот (Ctrl+C, заново `uvicorn`) — анкета НЕ должна сброситься
5. Введи телефон, адрес, гравировку
6. Получи подтверждение с номером заказа
7. Проверь что оба админа получили уведомление в MAX

Скриншоты: каждый шаг анкеты + подтверждение + уведомление админу.

### Шаг 3: проверка + Session Record + стоп.
```

**После F07 — Промпт №10.**

---

## Промпт №10 — F08 Менеджер и помощь

**Кому:** агенту
**Когда:** после F07

```markdown
F07 закрыта. Открываем **F08 — Менеджер и помощь**.

Шаг 1: feature_list.json — F08 in_progress.

Шаг 2:

### src/bot/handlers/info.py

- `handle_contact(client, chat_id, message_id)` — текст контактов + inline кнопки
- `handle_help(client, chat_id, message_id)` — текст помощи + inline кнопки

Тексты — точно по docs/TZ.md раздел 3.F08.

Inline кнопки контактов:
- [📱 Позвонить] → URL `tel:+79608627788`
- [🌐 VK] → URL из settings.manager_vk_link
- [💬 Написать в MAX] — показывать ТОЛЬКО если settings.max_manager_link непустой
- [🏠 Главная]

### Callback patterns
- `contact` — открыть контакты
- `help` — открыть помощь

### Расширь router.py
- Команды `/contact`, `/help` → соответствующие handlers
- Callback `contact` и `help` → handlers через edit_message

### Тесты
- test_info.py:
  - /contact возвращает текст с телефоном
  - /contact включает inline кнопки tel/VK
  - Если max_manager_link пуст — кнопка MAX отсутствует
  - /help возвращает справку с командами

### Ручной тест

1. /contact → видишь блок контактов с кнопками
2. Нажми VK — открывается ссылка
3. /help → справка

### Шаг 3: проверка + Session Record + стоп.
```

**После F08 — Промпт №11.**

---

## Промпт №11 — F09 Проверка подписки на канал

**Кому:** агенту
**Когда:** после F08

```markdown
F08 закрыта. Открываем **F09 — Проверка подписки на канал**.

Шаг 1: feature_list.json — F09 in_progress.

Шаг 2:

### src/services/subscription_service.py

```python
async def check_subscription(client, user_id: int | str) -> bool:
    """True если пользователь подписан на канал из settings.max_required_channel.
    Если max_required_channel пуст — gate отключён, всегда возвращает True."""

    settings = get_settings()
    if not settings.max_required_channel:
        return True

    member = await client.get_chat_member(settings.max_required_channel, user_id)
    if not member:
        return False

    status = member.get("status", "left")
    return status in ("member", "creator", "administrator")
```

### src/bot/handlers/subscription.py

```python
async def show_subscription_gate(client, chat_id, message_id):
    """Экран «подпишитесь на канал»."""
    text = "📢 Чтобы оформить заказ, подпишитесь на наш канал в MAX\n\nТам скидки, новинки и идеи гравировок."
    keyboard = [
        [{"text": "📢 Перейти в канал", "url": settings.max_required_channel_url}],
        [{"text": "✅ Я подписался", "callback_data": "sub:check"}],
        [{"text": "🔙 Назад в корзину", "callback_data": "cart"}],
    ]
    await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)


async def recheck_subscription(client, chat_id, user_id, message_id):
    """Повторная проверка."""
    if await check_subscription(client, user_id):
        # → запускаем FSM оформления (переадресация в order.py)
        await order_handler.start_checkout_flow(client, chat_id, user_id, message_id)
    else:
        await client.answer_callback_query(callback_id=..., notification="Подписка не найдена. Попробуйте через минуту.")
```

### Интеграция с F07

В `cart.py`, при callback `checkout`, перед `start_checkout_flow`:
```python
if not await check_subscription(client, user_id):
    await show_subscription_gate(client, chat_id, message_id)
    return
await start_checkout_flow(...)
```

### Callback patterns
- `sub:check` — повторная проверка

### Тесты
- test_subscription.py:
  - Пустой config → check_subscription возвращает True
  - Подписан (status="member") → True
  - Не подписан (status="left") → False
  - Канал не найден (member is None) → False
  - В сценарии checkout: gate показывается если не подписан

### Ручной тест

1. С пустым MAX_REQUIRED_CHANNEL → checkout запускает FSM сразу
2. Заполни MAX_REQUIRED_CHANNEL=`@свой_канал`, перезапусти бот
3. Не подписан → checkout показывает гейт
4. Подпишись на канал → нажми «Я подписался» → FSM запускается
5. Скриншот гейта.

### Шаг 3: проверка + Session Record + стоп.
```

**После F09 — Промпт №12.**

---

## Промпт №12 — F10 Админ-панель

**Кому:** агенту
**Когда:** после F09

```markdown
F09 закрыта. Открываем **F10 — Админ-панель**.

Шаг 1: feature_list.json — F10 in_progress.

Шаг 2:

### Защита доступа

В начале admin handler:
```python
def is_admin(user_id) -> bool:
    return str(user_id) in get_settings().admin_ids_list
```

### src/services/admin_service.py

CRUD-обёртки для админских операций:
- `add_product(session, category_slug, title, price, description, cover_url, photo_urls)` → Product
- `update_product(session, product_id, **kwargs)`
- `delete_product(session, product_id)`
- `toggle_product_active(session, product_id)`
- `list_pending_orders(session)` / `update_order_status(session, order_id, status)`
- `broadcast_message(session, client, text)` — простая рассылка по всем User

### src/bot/handlers/admin.py

Главное меню `/admin`:
```
🛠 Админ-панель
[ 📦 Заказы ]    [ 📚 Товары ]
[ 🏷 Категории ] [ 📊 Статистика ]
[ 📤 Рассылка ]  [ 🚪 Выход ]
```

Подменю товаров:
- Список товаров по категориям
- Кнопки для каждого товара: [✏️] [🗑] [👁/🚫]
- Кнопка [➕ Добавить товар] → FSM admin:waiting_*

Подменю заказов:
- Списки по статусам
- Карточка заказа: товары, клиент, контакты + [✅ Завершить] [❌ Отменить]

### Admin FSM (для добавления товара)

States: `admin:add:category`, `:title`, `:price`, `:description`, `:photos`, `:preview`

После ввода фото-URL (несколько строк через newline) → превью с обычной карточкой → [✅ Сохранить] [✏️ Редактировать] [🔙 Отмена]

### Callback patterns
- `admin` — главное меню
- `admin:orders`, `admin:products`, `admin:categories`, `admin:stats`, `admin:broadcast`
- `admin:order:{id}`, `admin:order:{id}:complete`, `admin:order:{id}:cancel`
- `admin:product:add`, `admin:product:{id}:edit`, `admin:product:{id}:delete`, `admin:product:{id}:toggle`

### Тесты
- test_admin.py:
  - is_admin возвращает True для админских ID, False для остальных
  - Обычный пользователь /admin → no access (молча игнорируется или сообщение об ошибке)
  - add_product создаёт Product + ProductPhoto
  - update_order_status меняет статус и updated_at
  - broadcast_message отправляет всем User

### Ручной тест

1. Войди под обычным юзером, /admin → ничего не работает
2. Войди под админом (твой user_id из MAX_ADMIN_USER_IDS), /admin → видишь меню
3. 📚 Товары → 🔗 Браслеты → видишь товар → ✏️ → отредактируй цену → сохрани
4. ➕ Добавить товар → пройди FSM, добавь тестовый товар → проверь, что он появился в каталоге
5. 📦 Заказы → выбери заказ из F07 → ✅ Завершить → проверь что статус изменился

### Шаг 3: проверка + Session Record + стоп.
```

**После F10 — Промпт №13.**

---

## Промпт №13 — F11 Healthcheck + логирование

**Кому:** агенту
**Когда:** после F10

```markdown
F10 закрыта. Открываем **F11 — Healthcheck + логирование**.

Шаг 1: feature_list.json — F11 in_progress.

Шаг 2:

### Расширь src/bot/webhook.py

```python
@router.get("/health")
async def health() -> dict:
    """Проверка живости приложения, БД и MAX API."""
    db_ok = await _check_db()
    max_ok = await _check_max_api()
    return {
        "status": "ok" if db_ok and max_ok else "degraded",
        "db": "ok" if db_ok else "fail",
        "max_api": "ok" if max_ok else "fail",
        "uptime_seconds": int(time.time() - START_TIME),
    }
```

### Расширь src/main.py

Настрой logging нормально:

```python
import logging
import sys

def setup_logging():
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    ))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
```

Вызови `setup_logging()` в начале main.py.

### Тесты
- test_health.py:
  - GET /health возвращает 200 со status, db, max_api, uptime_seconds
  - Если БД недоступна → status="degraded"

### Шаг 3: проверка + Session Record + стоп.
```

**После F11 — Промпт №14.**

---

## Промпт №14 — F12 Деплой (production)

**Кому:** ты + агенту (поэтапно)
**Когда:** после F11

> Эта фича — НЕ кодинг, это операции на сервере. Агент помогает с конфигами, ты выполняешь команды.

### Шаг 1: ты — арендуй VPS

- Любой провайдер: TimeWeb, Selectel, REG.RU
- Минимум 1GB RAM, Ubuntu 22.04 или 24.04
- Купи домен или используй поддомен (нужен HTTPS)
- Прокинь A-запись с домена на IP сервера

### Шаг 2: ты — подготовка сервера

```bash
# SSH на сервер
ssh root@<server_ip>

# Обновление
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx git ufw postgresql postgresql-contrib

# Создать пользователя
adduser astralaser
usermod -aG sudo astralaser
su - astralaser

# Клонировать репо
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/ВАШ_ЛОГИН/astralaser-max-bot-v2.git
cd astralaser-max-bot-v2

# venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env (production)
nano .env
# Заполни: реальный токен, прод PostgreSQL URL, домен, реальные ID админов
```

### Шаг 3: PostgreSQL

```bash
sudo -u postgres psql
CREATE DATABASE astralaser_prod;
CREATE USER astralaser_user WITH PASSWORD 'СГЕНЕРИРУЙ_ПАРОЛЬ';
GRANT ALL PRIVILEGES ON DATABASE astralaser_prod TO astralaser_user;
\q

# В .env:
# DATABASE_URL=postgresql+asyncpg://astralaser_user:ПАРОЛЬ@localhost:5432/astralaser_prod
```

Прогон миграций и seed:
```bash
python -m alembic upgrade head
python scripts/seed_db.py
```

### Шаг 4: Промпт агенту — конфиг nginx + systemd

```markdown
F12 — деплой. Помоги с конфигами:

1. Создай файл deploy/nginx-astralaser.conf:

```nginx
server {
    listen 80;
    server_name astrabot.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name astrabot.example.com;

    ssl_certificate /etc/letsencrypt/live/astrabot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/astrabot.example.com/privkey.pem;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

2. Создай deploy/astralaser-bot.service (systemd unit):

```ini
[Unit]
Description=Astralaser MAX Bot
After=network.target postgresql.service

[Service]
Type=simple
User=astralaser
Group=astralaser
WorkingDirectory=/home/astralaser/projects/astralaser-max-bot-v2
EnvironmentFile=/home/astralaser/projects/astralaser-max-bot-v2/.env
ExecStart=/home/astralaser/projects/astralaser-max-bot-v2/venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Создай deploy/DEPLOY.md с пошаговой инструкцией для меня.
```

### Шаг 5: ты — установка (по DEPLOY.md от агента)

```bash
# nginx
sudo cp deploy/nginx-astralaser.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/nginx-astralaser.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Let's Encrypt
sudo certbot --nginx -d astrabot.example.com

# systemd
sudo cp deploy/astralaser-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable astralaser-bot
sudo systemctl start astralaser-bot
sudo systemctl status astralaser-bot

# firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# регистрация webhook
cd ~/projects/astralaser-max-bot-v2
source venv/bin/activate
python scripts/set_webhook.py
```

### Шаг 6: проверка

```
curl https://astrabot.example.com/health
# должно: {"status": "ok", ...}
```

В MAX: `/start` → бот отвечает.

### Шаг 7: финальный Session Record + закрытие F12

Запиши:
- Сервер, домен (без чувствительных данных в repo)
- Что развёрнуто
- Webhook URL зарегистрирован
- Бот ответил на тестовый /start

### Финальный коммит

```bash
git commit -am "feat(F12): production deployment with nginx + systemd + Let's Encrypt"
git push
```

🎉 Проект готов.
```

---

## Что после F12

1. **Передай боту клиенту** — пусть тестирует.
2. **Заведи второй чат у агента**: фичи F13+ (отзывы, аналитика, скидка 10% за подписку, рассылки) — для будущих итераций.
3. **Backup БД**: настрой `pg_dump` по cron.
4. **Мониторинг**: подключи UptimeRobot на `/health` или Healthchecks.io.
5. **Логи**: `journalctl -u astralaser-bot -f` — смотри онлайн.

---

## Шпаргалка: команды на каждый день

```powershell
# Локально
.\venv\Scripts\Activate.ps1
python -m pytest -v
python -m ruff check . --fix
python -m mypy src/
python -m uvicorn src.main:app --reload

# Перед коммитом
.\init.ps1
git status
git diff --stat
git add -A
git commit -m "..."
git push

# На сервере
ssh astralaser@server
cd ~/projects/astralaser-max-bot-v2
git pull
source venv/bin/activate
python -m alembic upgrade head
sudo systemctl restart astralaser-bot
sudo systemctl status astralaser-bot
journalctl -u astralaser-bot -n 100
```

---

**Версия плейбука:** 2.0
**Дата:** 2026-05-06
