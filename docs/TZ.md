# Техническое задание: Astralaser MAX Bot v2.0

**Версия:** 2.0
**Дата:** 2026-05-06
**Заказчик:** Astralaser (украшения с персональной гравировкой)
**Платформа:** MAX мессенджер (`https://max.ru`)
**Стек:** Python 3.11 + FastAPI (webhook) + SQLAlchemy async + SQLite/PostgreSQL

---

## 1. Цель проекта

Создать профессионального бота-магазина для мессенджера MAX, который:
- Показывает каталог украшений с гравировкой (категории, карточки, фото-галерея)
- Принимает заказы (с FSM-анкетой: ФИО, телефон, адрес)
- Уведомляет менеджера о новых заказах
- Имеет встроенную админ-панель для управления товарами
- Проверяет подписку на канал перед оформлением заказа
- Не плодит сообщения в чате (использует подмену через `edit_message`)

## 2. Технические требования

### 2.1 Стек

| Компонент | Версия / технология |
|-----------|---------------------|
| Python | 3.11 |
| Web framework | FastAPI 0.110+ (для webhook endpoint) |
| HTTP клиент | httpx (async) |
| ORM | SQLAlchemy 2.x async |
| Миграции | Alembic |
| БД (dev) | SQLite + aiosqlite |
| БД (prod) | PostgreSQL + asyncpg |
| Конфиг | pydantic-settings |
| Тесты | pytest + pytest-asyncio |
| Качество | ruff + mypy |
| Деплой | nginx + systemd + Let's Encrypt + ufw |

### 2.2 Транспорт MAX API

**Только webhook** (long polling запрещён — лимиты 2 RPS / 30s с 11.05.2026).

**Авторизация:** только заголовок `Authorization: <MAX_BOT_TOKEN>`.
Передача токена через query-параметр `?access_token=...` запрещена.

**Базовый URL API:** `https://platform-api.max.ru`

**Регистрация webhook:**
- `POST /subscriptions?url=https://your-domain.com/webhook` — при старте бота
- `DELETE /subscriptions?url=...` — при остановке (опционально)

**Endpoint в нашем боте:** `POST /webhook` принимает JSON от MAX, отвечает 200 OK мгновенно (обработка в фоне через `asyncio.create_task` или `BackgroundTasks` FastAPI).

### 2.3 Архитектура (5 слоёв harness)

```
┌───────────────────────────────────────────────┐
│  Layer 1: Спецификация задачи                 │
│  → docs/TZ.md, feature_list.json              │
├───────────────────────────────────────────────┤
│  Layer 2: Контекст для агента                 │
│  → AGENTS.md, CLAUDE.md, progress.md          │
├───────────────────────────────────────────────┤
│  Layer 3: Среда исполнения                    │
│  → .env, init.ps1, init.sh, alembic           │
├───────────────────────────────────────────────┤
│  Layer 4: Верификация                         │
│  → tests/, ruff, mypy, DoD checklist          │
├───────────────────────────────────────────────┤
│  Layer 5: Управление состоянием               │
│  → DB (UserState FSM), git, progress.md       │
└───────────────────────────────────────────────┘
```

### 2.4 Структура кода (строгая)

```
astralaser-max-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                  # Запуск FastAPI приложения
│   ├── config.py                # Pydantic Settings
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── max_client.py        # HTTP клиент MAX API
│   │   ├── router.py            # Роутинг updates → handlers
│   │   ├── keyboards.py         # Inline клавиатуры
│   │   ├── webhook.py           # FastAPI endpoint /webhook
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── start.py         # /start, политика, главное меню
│   │       ├── catalog.py       # Каталог, категории, карточки, пагинация
│   │       ├── cart.py          # Корзина
│   │       ├── order.py         # Оформление заказа (FSM)
│   │       ├── info.py          # /contact, /help
│   │       ├── subscription.py  # Проверка подписки на канал
│   │       └── admin.py         # Админ-панель
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── catalog_service.py
│   │   ├── cart_service.py
│   │   ├── order_service.py
│   │   ├── fsm_service.py       # Persistent FSM в БД
│   │   ├── subscription_service.py
│   │   └── admin_service.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py            # async engine + session
│   │   ├── models.py            # SQLAlchemy модели
│   │   └── crud/
│   │       ├── __init__.py
│   │       ├── user.py
│   │       ├── category.py
│   │       ├── product.py
│   │       ├── product_photo.py
│   │       ├── cart.py
│   │       ├── order.py
│   │       └── user_state.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Фикстуры
│   ├── test_models.py
│   ├── test_crud.py
│   ├── test_handlers.py
│   ├── test_max_client.py
│   ├── test_router.py
│   ├── test_webhook.py
│   ├── test_cart.py
│   ├── test_order.py
│   ├── test_admin.py
│   └── test_subscription.py
├── scripts/
│   ├── seed_db.py               # Идемпотентный seed
│   └── set_webhook.py           # Регистрация webhook на MAX
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── data/
│   ├── seed_products.json       # Источник правды по товарам
│   └── photos/                  # (опционально, локальное кеширование)
├── docs/
│   ├── TZ.md                    # Это ТЗ
│   ├── PROMPTS.md               # PROMPT_PLAYBOOK
│   └── HANDOFF.md               # Инструкция handoff между агентами
├── .env.example
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── AGENTS.md                    # Для Codex/Kimi/DeepSeek
├── CLAUDE.md                    # Для Claude Code
├── feature_list.json            # Реестр фич
├── progress.md                  # Лог сессий
├── README.md
├── init.ps1                     # Windows: проверка готовности
├── init.sh                      # Linux: проверка готовности
└── astralaser-bot.service       # systemd unit (для деплоя)
```

**Архитектурные правила (СТРОГО):**

1. **Слои вызываются строго сверху вниз:** `webhook` → `router` → `handlers` → `services` → `crud` → `db`. Никаких обратных вызовов.
2. **Handlers не импортируют CRUD напрямую.** Только через services.
3. **Services не импортируют MAX API клиент.** Они работают только с DB и возвращают DTO/dataclasses.
4. **Все настройки через `src/config.py`** (Pydantic Settings). Никаких хардкодов.
5. **Все user-facing тексты на русском.**
6. **Handlers используют `edit_message` где возможно** (подмена), `send_message` — только когда невозможно (новый экран после действия пользователя).

## 3. Функциональные требования (фичи)

### F00 — Инфраструктура и harness

- Создание структуры проекта
- `pyproject.toml` с зависимостями
- `.gitignore`, `.env.example`
- `AGENTS.md`, `CLAUDE.md`, `feature_list.json`, `progress.md`
- `init.ps1` и `init.sh` для проверки готовности
- Базовый `pytest` setup, `ruff`, `mypy`

**DoD:** `python -m pytest -q` отрабатывает (даже на пустых тестах), `ruff check .` clean, `mypy src/` clean, репозиторий закоммичен.

### F01 — БД, модели, миграции, seed

**Таблицы:**

```python
class User:
    id: int                    # PK
    max_user_id: str           # UNIQUE, идентификатор пользователя в MAX
    username: str | None
    full_name: str | None
    consent_at: datetime | None  # Когда принял политику
    created_at: datetime

class Category:
    id: int
    title: str                 # "Колье и кулоны"
    slug: str                  # "kole-i-kulony" (UNIQUE)
    description: str | None
    sort_order: int
    is_active: bool
    created_at: datetime

class Product:
    id: int
    category_id: int           # FK
    title: str
    description: str
    price: int                 # копейки или рубли (фикс — рубли)
    cover_url: str
    is_active: bool
    sort_order: int
    created_at: datetime

class ProductPhoto:
    id: int
    product_id: int            # FK, cascade delete
    url: str
    sort_order: int            # 0..N

class CartItem:
    id: int
    user_id: int               # FK
    product_id: int            # FK
    quantity: int
    created_at: datetime
    UNIQUE(user_id, product_id)

class Order:
    id: int
    user_id: int               # FK
    customer_name: str
    customer_phone: str
    delivery_address: str
    total_amount: int
    status: str                # "pending", "confirmed", "completed", "cancelled"
    notes: str | None          # пожелания клиента, гравировка
    created_at: datetime
    updated_at: datetime

class OrderItem:
    id: int
    order_id: int              # FK, cascade delete
    product_id: int            # FK
    product_title_snapshot: str  # snapshot названия на момент заказа
    price_snapshot: int          # snapshot цены
    quantity: int

class UserState:
    user_id: int               # PK (FK на User)
    state: str                 # "order:waiting_name", "admin:waiting_title", ...
    data: str                  # JSON с накопленными данными
    updated_at: datetime
```

**Миграции:** одна initial миграция со всеми таблицами.

**Seed (`scripts/seed_db.py`):**
- Идемпотентный (повторный запуск не дублирует)
- Читает `data/seed_products.json` (см. отдельный файл)
- Создаёт 3 категории, 4 товара, 22 фото

**DoD:** `python -m alembic upgrade head` отрабатывает, `python scripts/seed_db.py` создаёт записи и при повторном запуске говорит `new_products=0`. Тесты `test_models.py`, `test_crud.py` зелёные.

### F02 — Транспорт MAX API (max_client.py)

**Класс `MAXClient`:**

```python
class MAXClient:
    def __init__(self, token: str, base_url: str = "https://platform-api.max.ru"):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token},  # ВАЖНО: Authorization, не access_token!
            timeout=30,
        )

    async def send_message(chat_id, text, reply_markup=None, photo_url=None) -> dict
    async def edit_message(chat_id, message_id, text, reply_markup=None, photo_url=None) -> dict
    async def delete_message(chat_id, message_id) -> bool
    async def answer_callback_query(callback_id, notification=None) -> bool  # graceful 4xx
    async def subscribe_webhook(url: str) -> bool   # POST /subscriptions
    async def unsubscribe_webhook(url: str) -> bool # DELETE /subscriptions
    async def get_chat_member(chat_id, user_id) -> dict | None  # для проверки подписки
```

**Формат payload (важно — выяснили опытным путём):**
- Текст: `{"text": "..."}`
- Фото: использовать `attachments: [{"type": "image", "payload": {"token": "<upload_token>"}}]` через upload flow.
- Альтернативно (если upload не требуется): `{"text": "...", "attachments": [{"type": "image", "payload": {"url": "..."}}]}` — проверить опытным путём в первой live-сессии и зафиксировать в `progress.md`.
- Inline-клавиатура: `attachments: [{"type": "inline_keyboard", "payload": {"buttons": [[...]]}}]`

**DoD:** unit-тесты с моками `httpx.MockTransport` на каждый метод; ошибки 4xx логируются как `warning`, не убивают процесс.

### F03 — Webhook + точка входа

**`src/main.py`:**
```python
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from src.bot.webhook import router as webhook_router
from src.bot.max_client import MAXClient
from src.config import get_settings

app = FastAPI(title="Astralaser MAX Bot")
app.include_router(webhook_router)

@app.on_event("startup")
async def on_startup():
    settings = get_settings()
    client = MAXClient(settings.max_bot_token)
    await client.subscribe_webhook(settings.webhook_url)

@app.on_event("shutdown")
async def on_shutdown():
    # опционально отписка
    pass

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000)
```

**`src/bot/webhook.py`:**
```python
@router.post("/webhook")
async def receive_update(request: Request, background: BackgroundTasks):
    payload = await request.json()
    background.add_task(process_update, payload)
    return {"ok": True}
```

**DoD:** локально работает через ngrok / pinggy, MAX доставляет update, бот отвечает.

### F04 — Главное меню + политика конфиденциальности

**Поток:**

1. Пользователь пишет `/start`
2. Если у него `consent_at IS NULL` → показать политику конфиденциальности с кнопкой `[✅ Принимаю] [❌ Отклонить]`
3. После `[✅ Принимаю]` → записать `consent_at`, показать главное меню (фото + текст + клавиатура)
4. После `[❌ Отклонить]` → ответить «Без согласия мы не можем продолжить. Вы всегда можете вернуться, нажав /start»

**Текст политики (короткая версия):**

```
🔒 Перед тем как продолжить

Мы храним только данные, необходимые для обработки заказа: ваш ID в MAX, имя, телефон и адрес доставки.

Мы НЕ передаём данные третьим лицам. Вы можете удалить свои данные, написав менеджеру.

Полная версия политики: https://astralazer.ru/privacy

Подтверждая, вы соглашаетесь с обработкой персональных данных.
```

**Главное меню (`/start` после согласия):**

Caption (без URL в тексте!):
```
🌟 Astralaser — украшения с персональной гравировкой

Здесь вы можете заказать кулоны, браслеты и брелоки с индивидуальной гравировкой для себя или в подарок.

Мы поможем подобрать изделие, согласуем ваш текст и изготовим украшение специально под ваш заказ.

✨ Срок изготовления: 1–2 рабочих дня
📦 Доставка СДЭК по всей России
💝 Бархатная сумочка в комплекте

Выберите раздел, чтобы начать.
```

Reply-клавиатура (нижняя):
```
[ 📚 Каталог ]    [ 🛒 Корзина ]
[ 📦 Мои заказы ] [ ❓ Помощь  ]
[ 💬 Менеджер ]
```

**DoD:** при первом `/start` показывается политика, пока не нажал `[✅ Принимаю]` — главное меню недоступно. После согласия второй `/start` сразу показывает меню.

### F05 — Каталог: категории, карточки, пагинация фото

**Поток:**

1. `[📚 Каталог]` или `/catalog` → показать **редактируемое сообщение** с inline-кнопками категорий:
   ```
   Выберите категорию:
   [ 📿 Колье и кулоны ]
   [ 🔗 Браслеты ]
   [ 🔑 Брелоки ]
   [ 🔙 В главное меню ]
   ```

2. Клик по категории → редактирование того же сообщения, показ списка товаров категории:
   - Если 1 товар: сразу открыть карточку (см. п. 3)
   - Если N товаров: показать список с кнопками `[1] [2] [3] ... [🔙 Назад]`

3. Карточка товара (фото + caption + клавиатура):
   ```
   📿 Кулон-столбик с гравировкой
   💰 840 ₽

   Кулон-столбик с секретным посланием — открывается, внутри гравировка ваших слов...

   [короткое описание, ~250 симв]
   ```

   Клавиатура:
   ```
   [ ◀️ Фото 2/6 ▶️ ]
   [ 🛒 В корзину ]
   [ 🔙 К категории ] [ 🏠 Главная ]
   ```

4. Клик `◀️` / `▶️`: **редактирование сообщения** с заменой `photo_url` на следующий/предыдущий из `ProductPhoto`. Циклически: с последнего → на первый.

5. Клик `[🛒 В корзину]`: добавить в БД, показать `🔔 Уведомление` callback (если работает) или `edit_message` с временным текстом «Добавлено ✅», кнопки: `[🛒 К корзине]` `[← Назад к товару]` `[🏠 Главная]`.

**Callback patterns:**
- `cat:{slug}` — открыть категорию
- `prod:{id}` — открыть карточку товара
- `photo:{id}:{idx}` — переключить фото (idx = sort_order следующего/предыдущего)
- `add:{id}` — добавить в корзину
- `home` — в главное меню

**DoD:** все 3 категории работают, карточки рендерятся с правильным фото, пагинация листает циклически, добавление в корзину работает, кнопка `🔙` всегда возвращает на предыдущий экран через `edit_message`.

### F06 — Корзина

**Поток:**

1. `[🛒 Корзина]` или `/cart` → показать **редактируемое сообщение**:
   ```
   🛒 Ваша корзина

   1. Кулон-столбик
      840 ₽ × 1 = 840 ₽
      [➖] [➕] [❌]

   2. Браслет с гравировкой
      940 ₽ × 2 = 1880 ₽
      [➖] [➕] [❌]
   ──────────────
   Итого: 2 720 ₽

   [ ✅ Оформить заказ ]
   [ 🗑 Очистить ] [ 🏠 Главная ]
   ```

2. Если корзина пуста:
   ```
   🛒 Корзина пуста.
   Загляните в каталог, чтобы выбрать украшение.

   [ 📚 К каталогу ] [ 🏠 Главная ]
   ```

**Callback patterns:**
- `qty:{product_id}:inc` — +1
- `qty:{product_id}:dec` — −1 (если 0 → удалить)
- `rm:{product_id}` — удалить
- `clear` — очистить (с подтверждением)
- `checkout` — перейти к оформлению

**DoD:** добавление, изменение, удаление работают; всё через `edit_message` (одно сообщение); итог считается корректно.

### F07 — Оформление заказа (FSM)

**Поток (persistent FSM в `UserState`):**

1. `[✅ Оформить заказ]` → проверить корзину не пуста.
2. Перейти в `state="order:waiting_name"`, спросить:
   ```
   Шаг 1/4: Как вас зовут?
   Напишите ФИО (например: Иванов Иван Иванович)
   [ ❌ Отмена ]
   ```
3. После сообщения с именем → `state="order:waiting_phone"`:
   ```
   Шаг 2/4: Ваш номер телефона?
   Формат: +7 XXX XXX XX XX
   [ ❌ Отмена ]
   ```
4. После телефона → `state="order:waiting_address"`:
   ```
   Шаг 3/4: Адрес доставки СДЭК
   Укажите город и пункт выдачи (или адрес курьерской доставки).
   [ ❌ Отмена ]
   ```
5. После адреса → `state="order:waiting_notes"`:
   ```
   Шаг 4/4: Что выгравировать?
   Напишите текст гравировки или пожелания (≤ 30 символов на грань).
   Если пока не знаете — напишите «обсудим с менеджером».
   [ ❌ Отмена ]
   ```
6. После заметок → создать `Order` + `OrderItems` (snapshot названия и цены), очистить корзину, очистить state, показать:
   ```
   ✅ Заказ #1234 принят!

   Сумма: 1 880 ₽
   Менеджер свяжется с вами в течение часа в рабочие часы (пн–сб 10:00–18:00 МСК).

   [ 📦 Мои заказы ] [ 🏠 Главная ]
   ```
7. Параллельно отправить уведомление в **обе админских чата** (`MAX_ADMIN_USER_IDS`):
   ```
   🔔 Новый заказ #1234

   👤 Иванов Иван
   📞 +7 999 123 45 67
   📍 Москва, СДЭК ул. Ленина 5

   📿 Кулон-столбик × 1 — 840 ₽
   🔗 Браслет × 1 — 940 ₽

   💰 Итого: 1 780 ₽

   ✏️ Гравировка: "Любимой"
   ```

**Валидация:**
- Имя: 2–100 символов, содержит хотя бы одно слово.
- Телефон: regex `^\+?\d[\d\s\-\(\)]{9,17}$`. Если не подошёл — попросить ещё раз.
- Адрес: 5–300 символов.
- Заметки: 0–500 символов.

**Callback `cancel`:** очистить state, вернуть в корзину.

**DoD:** анкета проходится за 4 шага, при перезапуске бота состояние сохраняется в `UserState`, заказ создаётся, корзина чистится, оба админа получают уведомление.

### F08 — Менеджер и помощь

**`/contact` или `[💬 Менеджер]`:**

```
💬 Связаться с менеджером

📱 Телефон: +7 903 348 92 05
🌐 ВКонтакте: vk.com/pk_astralazer
💬 MAX: написать менеджеру

🕐 Рабочие часы: пн–сб 10:00–18:00 МСК
```

Кнопки (inline):
- `[📱 Позвонить]` → `tel:+79033489205`
- `[🌐 VK]` → `https://vk.com/pk_astralazer`
- `[💬 Написать в MAX]` → ссылка из `MAX_MANAGER_LINK` в `.env` (если задана)
- `[🏠 Главная]`

**`/help` или `[❓ Помощь]`:**

```
❓ Помощь

Команды:
/start — начало
/catalog — каталог украшений
/cart — корзина
/orders — мои заказы
/contact — связаться с менеджером
/help — эта справка

Как сделать заказ:
1. Выберите категорию в каталоге
2. Откройте товар, нажмите «🛒 В корзину»
3. Перейдите в корзину → «Оформить заказ»
4. Заполните анкету (4 шага)
5. Менеджер свяжется и согласует макет гравировки

Срок изготовления: 1–2 рабочих дня
Доставка: СДЭК (ПВЗ или курьер)
```

### F09 — Проверка подписки на канал (gate перед оформлением)

**Концепция:** перед нажатием `[✅ Оформить заказ]` проверить, подписан ли пользователь на канал `MAX_REQUIRED_CHANNEL`.

**Поток:**

1. Клик `[✅ Оформить заказ]` (callback `checkout`)
2. Перед стартом FSM — вызов `max_client.get_chat_member(channel_chat_id, user_id)`
3. Если статус `member`/`creator`/`administrator` → разрешить (FSM запускается)
4. Если `left`/`kicked`/`null` → показать:
   ```
   📢 Чтобы оформить заказ, подпишитесь на наш канал в MAX

   Там скидки, новинки и идеи гравировок.

   [ 📢 Перейти в канал ] [ ✅ Я подписался ]
   [ 🔙 Назад ]
   ```
5. Клик `[✅ Я подписался]` → повторная проверка. Если подписан → запустить FSM. Если нет → ответить «Мы пока не видим подписку. Попробуйте через минуту.»

**Конфиг:** `MAX_REQUIRED_CHANNEL` в `.env`. Если пуст — фича отключена, бот сразу пускает в FSM.

**DoD:** при пустом `MAX_REQUIRED_CHANNEL` всё работает как раньше; при заданном — гейт работает; кнопка повторной проверки работает.

### F10 — Админ-панель

**Доступ:** только если `max_user_id` пользователя в списке `MAX_ADMIN_USER_IDS` (env, через запятую).

**Команда `/admin`:**

```
🛠 Админ-панель

[ 📦 Заказы ]    [ 📚 Товары ]
[ 🏷 Категории ] [ 📊 Статистика ]
[ 📤 Рассылка ] [ 🚪 Выход ]
```

**Подменю «📚 Товары»:**

```
📚 Управление товарами

[ ➕ Добавить товар ]
[ 📿 Колье и кулоны (2) ]
[ 🔗 Браслеты (1) ]
[ 🔑 Брелоки (1) ]
[ 🔙 Назад ]
```

Клик по категории → список товаров с кнопками `[✏️]` `[🗑]` `[👁/🚫]` (вкл/выкл `is_active`).

**Поток «➕ Добавить товар» (FSM `admin:waiting_*`):**

1. Выбор категории
2. Ввод названия
3. Ввод цены (число)
4. Ввод описания (до 1000 симв)
5. Загрузка фото (URL или несколько URL — поддержать парсинг строк)
6. Превью карточки
7. `[✅ Сохранить]` или `[🔙 Отменить]`

**Подменю «📦 Заказы»:**

```
📦 Заказы

[ 🟡 В работе (3) ]
[ ✅ Завершённые (12) ]
[ ❌ Отменённые (1) ]
[ 🔙 Назад ]
```

Клик по заказу → детали + кнопки `[✅ Завершить]` `[❌ Отменить]` `[💬 Связаться с клиентом]`.

**DoD:** обычный пользователь не имеет доступа (получает «команда не найдена»); админ может добавить, отредактировать, удалить, скрыть товар; админ видит заказы и меняет статус.

### F11 — Healthcheck + логирование

- `GET /health` → `{"status": "ok", "db": "ok", "max_api": "ok", "uptime": "..."}`
- Структурированное логирование (стандартный `logging` с форматом):
  ```
  2026-05-06T12:00:00Z INFO src.bot.router - update routed: type=callback, user=123
  ```
- Уровень `LOG_LEVEL` из `.env` (DEBUG / INFO / WARNING / ERROR)

### F12 — Деплой (production)

**Сервер:** Ubuntu 22.04+, минимум 1GB RAM.

**Шаги:**
1. Установить Python 3.11, nginx, certbot, postgresql
2. Клонировать репо в `/opt/astralaser-max-bot`
3. Создать venv, поставить зависимости
4. Создать `.env` с production значениями (PostgreSQL URL, реальный токен)
5. Прогнать миграции `alembic upgrade head`
6. Прогнать seed `python scripts/seed_db.py`
7. Поднять nginx с reverse proxy на `127.0.0.1:8000`
8. Получить SSL через `certbot --nginx -d astrabot.example.com`
9. Создать systemd unit `astralaser-bot.service`, запустить, добавить в автозагрузку
10. Зарегистрировать webhook через `python scripts/set_webhook.py`
11. ufw allow 22, 80, 443

**DoD:** бот работает 24/7, после `systemctl restart astralaser-bot` поднимается автоматически, webhook доставляет updates.

## 4. Данные товаров (для seed)

См. файл `data/seed_products.json`.

Сводно:

| Категория | Товар | Цена | Фото |
|-----------|-------|------|------|
| Колье и кулоны | Кулон-столбик с гравировкой | 840 ₽ | 6 |
| Колье и кулоны | Кулон-конверт с гравировкой | 840 ₽ | 5 |
| Браслеты | Браслет с гравировкой на силиконовом ремешке | 940 ₽ | 5 |
| Брелоки | Кожаный брелок с гравировкой | 940 ₽ | 6 |

## 5. Бизнес-правила

- **Часы работы менеджера:** пн–сб 10:00–18:00 МСК. В нерабочее время бот говорит, что «менеджер ответит в начале рабочего дня».
- **Доставка:** только СДЭК. Стоимость согласовывается отдельно с менеджером.
- **Гравировка:** до 30 символов на грань. Полная стоимость указана за гравировку всех 4 граней.
- **Оплата:** в две стадии (предоплата по согласованию + при получении в ПВЗ). Бот не интегрирован с эквайрингом — оплату согласовывает менеджер.
- **Сроки изготовления:** 1–2 рабочих дня после согласования макета.
- **Скидка 10%** за подписку на канал (только на первый заказ) — отдельная фича на будущее, не входит в MVP.

## 6. Контакты и идентификаторы

- **Телефон менеджера:** +7 903 348 92 05
- **VK:** https://vk.com/pk_astralazer
- **MAX (бот):** username будет получен при регистрации (`MAX_BOT_USERNAME`)
- **MAX (менеджер):** ссылка в `MAX_MANAGER_LINK` из `.env`
- **Админ user ID №1:** `4147438`
- **Админ user ID №2:** `73412011`
- **Канал для подписки:** задать в `MAX_REQUIRED_CHANNEL` (например, `@astralazer_official`)

## 7. Definition of Done (для каждой фичи)

Фича переходит из `in_progress` в `completed` только при выполнении всех пунктов:

1. ✅ Код написан, импортируется без ошибок
2. ✅ Все unit-тесты проходят: `python -m pytest -v`
3. ✅ Линтер чистый: `ruff check .`
4. ✅ Типы чистые: `mypy src/`
5. ✅ `init.ps1` (или `init.sh`) проходит до конца со статусом `READY`
6. ✅ Бот стартует и отвечает на тестовое сообщение в MAX (для UI-фич)
7. ✅ В `progress.md` создан Session Record с evidence (вывод команд, скриншоты)
8. ✅ Изменения закоммичены в git и запушены в origin/main

## 8. Запреты (что НЕЛЬЗЯ делать)

- ❌ Использовать `aiogram` или другие Telegram-библиотеки. Только кастомный httpx-клиент для MAX.
- ❌ Использовать long polling. Только webhook.
- ❌ Передавать токен через query (`?access_token=...`). Только заголовок `Authorization`.
- ❌ Хранить токены, пароли, реальные ID в коде или в `.env.example`. Только в `.env` (gitignored).
- ❌ Отправлять в чат каскад новых сообщений. По возможности — `edit_message`.
- ❌ Включать URL картинок в текст сообщения (caption). Картинка идёт отдельно через attachments.
- ❌ Закрывать фичу как `completed` без всех 8 пунктов DoD.
- ❌ Открывать вторую фичу `in_progress`, пока первая не закрыта.

## 9. Дорожная карта (приоритеты)

```
F00 → F01 → F02 → F03 → F04 → F05 → F06 → F07 → F08 → F09 → F10 → F11 → F12
```

Никаких параллельных фич. Каждая закрывается полностью перед следующей.

---

**Это ТЗ — источник истины №1.** Если в `progress.md` или `feature_list.json` есть конфликт с этим документом, исправляется не ТЗ, а тот документ. Изменения в ТЗ — отдельной фичей с подписью.
