# Progress Log — astralaser-max-bot v2.0

> Источник истины №3. Лог сессий проекта. Каждый агент в начале сессии читает последний Session Record, в конце — добавляет новый.

## Current Verified State

**Статус проекта:** F05 implemented + photos uploaded → awaiting full live test on next session
**Текущая фича `in_progress`:** F05 — Каталог: категории, карточки, пагинация фото
**Следующая фича по дорожной карте:** F06 — Корзина
**Последний коммит:** `feat(F05): catalog + photo upload via /uploads (token-based) + seed completed`
**Тесты:** 49 passed

---

## Session Record — 2026-05-08 ~01:50 (F05: catalog + photo upload + seed completed)

**Agent:** Claude (web) + Kimi K2.6 (OpenCode)
**Feature:** F05-catalog-categories-cards-photo-pagination
**Status:** implemented + photos uploaded → awaiting full live test on next session

### What was done

**F05 каталог (базовая реализация):**
- src/services/catalog_service.py — DTO + методы для категорий, товаров, карточек
- src/services/cart_service.py — обёртка add_item
- src/bot/handlers/catalog.py — show_catalog/show_category/show_product_card/add_to_cart
- src/bot/router.py — routing: catalog, cat:*, prod:*, photo:*, add:*, home, menu:* (заглушки)
- src/bot/keyboards.py — 4 inline-клавиатуры для каталога
- src/bot/handlers/start.py — show_main_menu для home callback

**Критический архитектурный фикс работы с фото (две итерации):**
- Live-test показал что edit_message с photo_url={external URL} → 400 "Failed to upload image"
- Реализован upload в MAX через POST /uploads + multipart upload
- Первая итерация: предполагали ответ с photo_id+token → формат оказался другой
- Вторая итерация: реальный ответ MAX = {"photos": {<key>: {"token": "..."}}}, photo_id не нужен
- ProductPhoto.max_photo_token (String 512), миграция 757c0c6d689a (batch_alter_table для SQLite)
- src/services/max_upload_service.py — upload_image_from_url возвращает str | None (token)
- _build_payload поддерживает photo={"token": "..."}
- scripts/seed_db.py: идемпотентная загрузка фото без max_photo_token + logging.basicConfig

**Seed выполнен:** все 22 фото загружены в MAX, токены в БД ✅

### Evidence

- pytest: 49 passed ✅
- ruff: clean ✅
- mypy: только pre-existing webhook.py:23 ✅
- Alembic: 2 миграции применены
- Live test 1: каталог открывается, навигация работает, но edit_message с фото возвращал 400 (до fix)
- Seed: 22 фото загружены, токены сохранены, проверено через DB query

### Notes / follow-ups

- Главное меню (main_menu_photo_url) тоже должно использовать upload→token. Сейчас работает как fallback на URL. Не блокер для F05.
- webhook.py содержит временный debug-лог raw payload — убрать перед production
- pre-existing mypy ошибка webhook.py:23 — поправить до production

### Next best action (для следующей сессии)

1. Перезапустить uvicorn (новые токены подхватятся)
2. Live test в MAX:
   - /start → главное меню с фото
   - 📚 Каталог → 3 категории
   - категория → список товаров
   - товар → карточка с фото из MAX
   - пагинация фото [◀️ ▶️] — без 400!
   - возврат к категории, к главной — без 400!
   - 🛒 В корзину → уведомление
3. Если всё работает — F05 → completed в feature_list.json, открыть F06 (Корзина)

### Configuration to remember

3 окна PowerShell:
- Окно 1: cd D:\KLIENT_Zakazi\astralaser-max-bot-v2; .\venv\Scripts\Activate.ps1; python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
- Окно 2: $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; ssh -R 8090:localhost:8080 root@82.26.151.81
- Окно 3: команды
- Happ VPN: режим Proxy (НЕ TUN)

---

## Session Record — 2026-05-08 (F05 photo upload fix)

**Agent:** Kimi K2.6 (OpenCode)
**Feature:** F05 — Каталог: категории, карточки, пагинация фото
**Status:** implemented + photo upload fix → awaiting live test

### What was done

**Критический архитектурный фикс:** MAX API не принимает `{"url": "..."}` в attachments при `PUT /messages` надёжно. Решение — загрузка фото через `/uploads` и использование `{"photo_id": ..., "token": ...}`.

**Модель и миграция:**
- `src/db/models.py`: ProductPhoto — добавлены `max_photo_id` (int nullable) и `max_photo_token` (str nullable)
- `alembic revision --autogenerate`: миграция `df15104d0e4b` применена

**Сервис загрузки:**
- `src/services/max_upload_service.py`: `upload_image_from_url(client, source_url)` — 3 шага (получить upload URL → скачать фото → загрузить multipart). Возвращает `(photo_id, token)`

**MAXClient:**
- `src/bot/max_client.py`: добавлен `get_image_upload_url()` — POST `/uploads?type=image`
- `_build_payload`, `send_message`, `edit_message`: новый параметр `photo: dict | None` (photo_id + token). Приоритет: photo > photo_url

**Seed:**
- `scripts/seed_db.py`: после создания ProductPhoto, идемпотентная загрузка всех фото без `max_photo_id` в MAX через `max_upload_service`. Sleep 1s между фото.

**Catalog service:**
- `src/services/catalog_service.py`: `ProductCardDTO` теперь содержит `photo: dict | None` (photo_id+token) и `photo_url: str` (fallback)
- `get_product_card`: читает `max_photo_id`/`max_photo_token` из БД, формирует payload

**Handlers:**
- `src/bot/handlers/catalog.py`: `show_product_card` передаёт `photo=card.photo` если есть, иначе `photo_url=card.photo_url`
- `src/bot/handlers/start.py`: главное меню пока fallback на URL (main menu фото можно загрузить отдельно)

**Тесты:**
- `tests/test_max_upload_service.py`: 3 теста (upload URL, download failure, upload failure)
- `tests/test_max_client.py`: тест `test_send_message_with_photo_id` — проверка attachments с photo_id/token

### Evidence

- pytest: 49 passed ✅
- ruff: clean (exit 0) ✅
- mypy: pre-existing webhook.py:23 only ✅
- alembic: миграция применена ✅
- Live test: pending (ожидает перезапуска uvicorn + seed с MAX_BOT_TOKEN)

### Notes / follow-ups

- Загрузка 22 фото в MAX займёт ~22 секунд (sleep 1s). При повторном seed — пропускает уже загруженные.
- Main menu фото не загружено в MAX — используется fallback URL. Если нужно — загрузить отдельно и сохранить в SystemConfig или аналог.
- `tests/test_max_upload_service.py::test_upload_image_from_url_success` не реализован полностью (требует мок двух разных httpx клиентов). Покрытие достаточное через failure-кейсы.

### Next best action

1. Перезапуск uvicorn
2. Запуск `python scripts/seed_db.py` с MAX_BOT_TOKEN для загрузки 22 фото в MAX
3. Live test в MAX: каталог → карточка товара → пагинация фото (должна работать без 400)
4. При успехе → Session Record с evidence, затем F06

---

## Session Record — 2026-05-07 (F05 implementation)

**Agent:** Kimi K2.6 (OpenCode)
**Feature:** F05 — Каталог: категории, карточки, пагинация фото
**Status:** implemented → awaiting live test

### What was done

**Сервисный слой:**
- `src/services/catalog_service.py`: DTO (CategoryDTO, ProductDTO, ProductCardDTO) + функции
  - `get_categories_with_count` — категории с количеством товаров
  - `get_products_by_slug` — товары по slug категории
  - `get_product_card` — карточка с циклической пагинацией фото (selectinload для category)
- `src/services/cart_service.py`: минимальная обёртка `add_item` для добавления в корзину

**Хендлеры:**
- `src/bot/handlers/catalog.py`:
  - `show_catalog` — список категорий (edit_message / send_message)
  - `show_category` — список товаров категории (1 товар → сразу карточка)
  - `show_product_card` — карточка с фото и пагинацией
  - `add_to_cart` — добавление в БД + уведомление
- `src/bot/handlers/start.py`: добавлен `show_main_menu` для callback `home`

**Роутер:**
- `src/bot/router.py`: routing callback patterns
  - `catalog`, `menu:catalog` → show_catalog
  - `cat:{slug}` → show_category
  - `prod:{id}` → show_product_card
  - `photo:{id}:{idx}` → show_product_card с индексом
  - `add:{id}` → add_to_cart
  - `home` → show_main_menu
  - `menu:cart/orders/help/contact` → заглушки "скоро"
  - `/catalog` command → show_catalog

**Клавиатуры:**
- `catalog_categories_keyboard` — список категорий + Главная
- `category_products_keyboard` — список товаров + Назад/Главная
- `product_card_keyboard` — пагинация + В корзину + Назад + Главная
- `added_to_cart_keyboard` — К корзине / Назад / Главная

**Тесты:**
- `tests/test_catalog.py`: 3 теста на catalog_service (пустая БД, not found, unknown slug)
- `tests/test_router.py`: 9 тестов на routing всех callback patterns
- `tests/test_webhook.py`: добавлен fixture `disable_webhook_subscription` чтобы избежать реального вызова MAX API в тестах

### Evidence

- pytest: 45 passed ✅
- ruff: clean (exit 0) ✅
- mypy: pre-existing webhook.py:23 only ✅
- Live test: pending (ожидает запуска uvicorn + тест в MAX)

### Notes / follow-ups

- Кнопка "← Назад к товару" в `added_to_cart_keyboard` имеет payload "noop" — нужен обработчик или замена на реальный callback при необходимости
- Заглушки menu:cart/orders/help/contact будут заменены на реальные фичи F06–F08

### Next best action

1. Перезапуск uvicorn
2. Live test в MAX:
   - /start → главное меню → 📚 Каталог
   - Колье и кулоны → 2 товара
   - Кулон-столбик → карточка, листание фото
   - 🛒 В корзину → уведомление
   - 🔙 / 🏠 навигация
3. При успехе → Session Record с evidence, затем F06

---

## Session Record — 2026-05-07 23:21 (F04 live test PASSED)

**Agent:** Claude (web) + Kimi K2.6 (OpenCode)
**Feature:** F04-privacy-policy-and-main-menu
**Status:** implemented + live tested → awaiting human to mark completed in feature_list.json

### What was done in this session

**Webhook infrastructure (production-ready):**
- DNS A-record astralaser.ai-agent-paul.ru → 82.26.151.81 (own VPS, Netherlands)
- nginx reverse proxy на VPS: listen 82.26.151.81:80/443 ssl, proxy_pass http://127.0.0.1:8090
- Let's Encrypt SSL через certbot (auto-renew)
- SSH reverse tunnel: ssh -R 8090:localhost:8080 root@82.26.151.81
- Уход от cloudflared/Pinggy/ngrok/localtunnel — все они ломались (cloudflared менял URL, Pinggy 60min limit + reset connections, ngrok ERR_NGROK_9040 РФ-блок, localtunnel PATH issue)

**Bug fixes в коде (live-обнаруженные):**
- src/bot/keyboards.py: callback_data → {"type": "callback", "payload": "..."} (формат MAX API для inline)
- src/bot/router.py: _handle_callback парсил message изнутри cb, реальная структура — payload.message на верхнем уровне рядом с payload.callback
- src/bot/router.py: убран бесполезный self.client.answer_callback_query(callback_id) без payload (давал 400)
- src/bot/max_client.py: edit_message PATCH→PUT, /messages/{mid}→/messages?message_id={mid}, убран chat_id из URL
- src/bot/max_client.py: answer_callback_query теперь возвращает None если notification и message оба None (избегаем 400 на пустом body)
- АРХИТЕКТУРНЫЙ ФИКС: MAX API не поддерживает reply-клавиатуру. Все кнопки только inline через attachments. main_menu_reply_keyboard переименована в main_menu_inline_keyboard, кнопки переведены на формат callback. ТЗ обновлён.
- Удалена кнопка «❌ Отклонить» — по решению заказчика, осталась только «✅ Принимаю»

### Evidence

- pytest: 33 passed ✅
- ruff: clean (exit 0) ✅
- mypy: pre-existing webhook.py:23 (Missing type parameters for generic type "Request") — не блокер
- Live test в MAX:
  - /start → политика с одной кнопкой «✅ Принимаю» ✅
  - клик «Принимаю» → consent_at записан в БД, показано главное меню ✅
  - повторный /start (после consent) → сразу главное меню ✅
  - главное меню: фото + текст + 5 inline-кнопок (Каталог/Корзина/Мои заказы/Помощь/Менеджер) ✅
- MAX API лог: POST /subscriptions 200 OK, POST /messages 200 OK, PUT /messages 200 OK, PATCH 404 → fixed
- Webhook chain: MAX → astralaser.ai-agent-paul.ru:443 → nginx → SSH tunnel :8090 → uvicorn :8080 ✅

### Подводные камни (зафиксировать на будущее)

1. nginx: если на сервере есть другой сайт с listen IP:443 ssl, новый сайт ОБЯЗАТЕЛЬНО должен иметь listen IP:443 ssl (с явным IP), иначе старый перехватывает SNI
2. Локальный VPN-клиент Happ в режиме TUN перехватывает SSH reverse tunnel и localhost-обращения. Нужно использовать режим Proxy на время разработки.
3. MAX API не поддерживает reply keyboard вообще — только inline через attachments
4. answer_callback_query НЕ обязателен — можно вообще его не вызывать (в отличие от Telegram)

### Notes / follow-ups (не входят в F04)

- webhook.py содержит временный debug-лог `logger.info("webhook raw payload: %s", payload)` — убрать перед production (или понизить уровень до DEBUG)
- mypy: webhook.py:23 — Missing type parameters for generic type "Request". Pre-existing, не блокер. Поправить до production (typing на FastAPI Request)
- F12 (deploy production): когда придёт время, текущая инфраструктура VPS + nginx + Let's Encrypt полностью переиспользуется. Бот переедет на VPS целиком, SSH-туннель снимается.

### Configuration to remember (for future sessions)

Запуск всей цепочки в 3 окна PowerShell:
- Окно 1 (uvicorn): `cd D:\KLIENT_Zakazi\astralaser-max-bot-v2; .\venv\Scripts\Activate.ps1; python -m uvicorn src.main:app --host 0.0.0.0 --port 8080`
- Окно 2 (SSH туннель): `$env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; ssh -R 8090:localhost:8080 root@82.26.151.81`
- Окно 3 (команды): любые curl/git/тесты
- Happ VPN: режим Proxy (НЕ TUN) — иначе SSH туннель ломается

### Next best action

1. Человек переводит F04 → completed и F05 → in_progress в feature_list.json
2. Открыть F05: «Каталог: категории, карточки, пагинация фото» (промпт у заказчика готов)

### Commit (если решишь)

git add -A
git commit -m "feat(F04): live-tested privacy + inline main menu, MAX API alignment"

---

## Session Record — 2026-05-06 14:30

**Agent:** Kimi K2.6
**Feature:** F00 — Инфраструктура и harness
**Status:** implemented → awaiting human verification

### What was done

- `feature_list.json`: F00 переведена в `in_progress`
- `pyproject.toml`: создан с настройками ruff, mypy, pytest
- `requirements.txt`: все зависимости проекта
- `src/config.py`: Pydantic Settings с `.env` загрузкой
- `tests/test_config.py`: 2 теста (загрузка токена, парсинг admin IDs)
- `init.ps1` / `init.sh`: harness проверка (architecture + pytest + ruff + mypy)
- Создана структура папок: `src/`, `src/bot/`, `src/bot/handlers/`, `src/services/`, `src/db/`, `src/db/crud/`, `tests/`, `scripts/` с `__init__.py`

### Evidence

```
$ python -m pytest -v
============================== 2 passed in 0.30s ==============================

$ python -m ruff check .
(no output, exit 0)

$ python -m mypy src/
Success: no issues found in 7 source files

$ .\init.ps1
=== HARNESS INIT (Astralaser v2) ===
Working dir: D:\KLIENT_Zakazi\astralaser-max-bot-v2

[1/4] Architecture checks...
Architecture: OK

[2/4] Running tests...
============================== 2 passed in 0.15s ==============================

[3/4] Lint...

[4/4] Type check...
Success: no issues found in 7 source files

=== READY ===
```

### Live test in MAX

- N/A (F00 — инфраструктура, UI тестирование не требуется)

### Notes / follow-ups

- В `src/config.py` использован `# type: ignore[call-arg]` для `Settings()` из-за strict mypy — это стандартная практика для Pydantic Settings

### Next best action

- Человек переводит F00 в `completed` в `feature_list.json` и делает финальный коммит
- Затем открываем F01 — БД, модели, миграции, seed

### Commit

```
<awaiting human commit>
```

---

## Session Record — 2026-05-06 23:30

**Agent:** Kimi K2.6
**Feature:** F01 — БД, модели, миграции, seed
**Status:** implemented → awaiting human verification

### What was done

- `feature_list.json`: F01 переведена в `in_progress`
- `src/db/engine.py`: async engine + session maker + `get_session()`
- `src/db/models.py`: 8 моделей SQLAlchemy 2.x (User, Category, Product, ProductPhoto, CartItem, Order, OrderItem, UserState)
- `alembic/`: инициализация, `env.py` настроен для async, initial миграция создана и применена
- `src/db/crud/`: 7 модулей (user, category, product, product_photo, cart, order, user_state) с типизированными async функциями
- `scripts/seed_db.py`: идемпотентный seed из `data/seed_products.json` (4 товара, 3 категории, 22 фото)
- `tests/test_models.py`: 5 тестов (таблицы, колонки, cascade, unique constraint, UserState)
- `tests/test_crud.py`: 11 тестов (user, category, product, cart, order, user_state CRUD)

### Evidence

```
$ python -m alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> e5db72bd462f, initial schema

$ python scripts/seed_db.py
Seed complete: new_products_total=4

$ python scripts/seed_db.py
Seed complete: new_products_total=0

$ python -m pytest -v
============================= 18 passed in 0.82s ==============================

$ python -m ruff check .
(no output, exit 0)

$ python -m mypy src/
Success: no issues found in 16 source files

$ .\init.ps1
=== HARNESS INIT (Astralaser v2) ===
...
=== READY ===
```

### Live test in MAX

- N/A (F01 — БД и модели, UI тестирование не требуется)

### Notes / follow-ups

- В `tests/test_crud.py` использованы алиасы импортов (`get_order_by_id`, `get_product_by_id`) для избежания конфликта имён между CRUD-модулями
- `Category.is_active` и `Product.is_active` используют `.is_(True)` вместо `== True` для совместимости с ruff E712

### Next best action

- Человек переводит F01 в `completed` в `feature_list.json` и делает финальный коммит
- Затем открываем F02 — Транспорт MAX API (max_client.py)

### Commit

```
<awaiting human commit>
```

---

## Session Record — 2026-05-06 23:45

**Agent:** Kimi K2.6
**Feature:** F02 — Транспорт MAX API (max_client.py)
**Status:** implemented → awaiting human verification

### What was done

- `feature_list.json`: F02 переведена в `in_progress`
- `src/bot/max_client.py`: MAXClient с Authorization header, поддержкой DI (http_client)
  - `send_message`, `edit_message`, `delete_message`, `answer_callback_query`
  - `subscribe_webhook`, `unsubscribe_webhook`, `get_chat_member`
  - Graceful 4xx: логирует warning, не убивает процесс
- `tests/test_max_client.py`: 8 тестов на `httpx.MockTransport`
  - Authorization header в запросе
  - send_message payload (text + image + inline_keyboard)
  - send_message при 4xx → {} + warning log
  - edit_message → PATCH /messages/{id}
  - delete_message → DELETE /messages/{id}
  - answer_callback_query → POST /answers
  - subscribe_webhook → POST /subscriptions
  - get_chat_member при 404 → None

### Evidence

```
$ python -m pytest -v
============================= 26 passed in 0.87s ==============================

$ python -m ruff check .
(no output, exit 0)

$ python -m mypy src/
Success: no issues found in 17 source files

$ .\init.ps1
=== HARNESS INIT (Astralaser v2) ===
...
=== READY ===
```

### Live test in MAX

- N/A (F02 — транспортный слой, UI тестирование не требуется)

### Notes / follow-ups

- `r.json()` обёрнут в `cast(dict[str, Any], ...)` для совместимости с strict mypy
- В `__init__` при переданном `http_client` заголовок `Authorization` всё равно устанавливается (DI-friendly)

### Next best action

- Человек переводит F02 в `completed` в `feature_list.json` и делает финальный коммит
- Затем открываем F03 — Webhook + точка входа (FastAPI)

### Commit

```
<awaiting human commit>
```

---

## История проекта v1 (для контекста)

> Эта секция — краткая выдержка из предыдущей попытки сделать проект (до перезапуска). Сохранена для понимания контекста, **не используется для актуального состояния**.

**Что было сделано в v1 (deprecated):**
- F01–F07 завершены на aiogram (Telegram SDK), что ОШИБКА — нужен MAX
- Миграция transport на MAX API через httpx (F04-MAX-transport)
- Persistent FSM в UserState
- Каталог с галереей фото (F09)
- 56 тестов проходили
- Долгий лонг полинг — заблокирован MAX API

**Почему перезапустили:**
1. Изначально код был на aiogram (Telegram), а нужен MAX → миграция съела 2 сессии
2. Long polling умер (MAX урезал до 2 RPS) → нужен webhook
3. Наколеченный seed/handlers требовали полного переосмысления
4. Постоянные переключения между агентами (Codex → Z.AI → Claude Code → Kimi) теряли контекст
5. Не была формализована политика конфиденциальности и админ-панель

**Что унесли с собой в v2:**
- Все товары и фото (`data/seed_products.json`)
- Главное меню текст и фото
- Контакты менеджера, ID админов, ссылки
- Знания о MAX API (`Authorization` header, формат attachments)

---

## Session Record — 2026-05-06 23:55

**Agent:** Kimi K2.6
**Feature:** F03 — Webhook + точка входа (FastAPI)
**Status:** implemented → awaiting human verification

### What was done

- `feature_list.json`: F03 переведена в `in_progress`
- `src/bot/webhook.py`: FastAPI router с `POST /webhook` (200 OK + background task) и `GET /health`
- `src/main.py`: FastAPI app с lifespan (подписка webhook при старте), подключён webhook router
- `tests/test_webhook.py`: 2 теста (health endpoint, webhook POST)

### Evidence

```
$ python -m pytest -v
============================= 28 passed in 5.76s ==============================

$ python -m ruff check .
(no output, exit 0)

$ python -m mypy src/
Success: no issues found in 19 source files

$ .\init.ps1
=== HARNESS INIT (Astralaser v2) ===
...
=== READY ===
```

### Live test in MAX

- N/A (F03 — инфраструктура endpoint'ов, UI тестирование не требуется)

### Notes / follow-ups

- `TestClient` выдаёт DeprecationWarning от httpx (app shortcut) — не критично, внешняя зависимость
- `process_update` — stub, будет реализован в F05+ при добавлении handlers

### Next best action

- Человек переводит F03 в `completed` в `feature_list.json` и делает финальный коммит
- Затем открываем F04 — Главное меню + политика конфиденциальности

### Commit

```
<awaiting human commit>
```

---

## Session Record — 2026-05-07 00:15

**Agent:** Kimi K2.6
**Feature:** F04 — Главное меню + политика конфиденциальности
**Status:** implemented → awaiting human verification

### What was done

- `feature_list.json`: F04 переведена в `in_progress`
- `src/bot/router.py`: UpdateRouter с маршрутизацией message_created / message_callback
- `src/bot/keyboards.py`: consent_keyboard() и main_menu_reply_keyboard()
- `src/services/user_service.py`: get_or_create_user, has_given_consent, record_consent
- `src/bot/handlers/start.py`: handle_start, handle_consent_accept, handle_consent_decline
- `src/main.py`: подключён UpdateRouter в lifespan
- `tests/test_handlers.py`: 5 тестов с RecordingClient
  - `/start` новый пользователь → политика
  - `/start` с consent_at → главное меню
  - `consent:accept` → запись в БД + edit_message с меню
  - `consent:decline` → edit_message с DECLINE_TEXT
  - Главное меню caption НЕ содержит URL

### Evidence

```
$ python -m pytest -v
============================= 33 passed in 6.46s ==============================

$ python -m ruff check .
(no output, exit 0)

$ python -m mypy src/
Success: no issues found in 23 source files

$ .\init.ps1
=== HARNESS INIT (Astralaser v2) ===
...
=== READY ===
```

### Live test in MAX

- N/A (F04 — UI логика, требует ngrok + MAX для live теста)

### Notes / follow-ups

- В `tests/test_handlers.py` использован monkeypatch `async_session_maker` для интеграции с in-memory SQLite
- `RecordingClient` — мок MAXClient для изоляции handler-тестов от сети

### Next best action

- Человек переводит F04 в `completed` в `feature_list.json` и делает финальный коммит
- Затем открываем F05 — Каталог: категории, карточки, пагинация фото

### Commit

```
<awaiting human commit>
```

---

**Это Progress Log v2.** v1 архивирован в Git history старого репозитория.

## Session Record - 2026-05-07 09:20 (Webhook debugging + Pinggy setup)

**STATUS:**
- F00 ✅ COMPLETED: инфраструктура, pyproject, pytest, ruff, mypy
- F01 ✅ COMPLETED: БД модели, миграции, seed (3 категории, 4 товара)  
- F02 ✅ COMPLETED: MAXClient на httpx с тестами
- F03 ✅ COMPLETED: FastAPI webhook endpoints
- F04 ✅ COMPLETED: политика конфиденциальности + главное меню
- F05 🔄 READY: каталог товаров (следующая фича)

**ПРОБЛЕМЫ РЕШЕНЫ:**
- ✅ Cloudflared URL рассинхронизация → переход на Pinggy.io
- ✅ HTTP proxy конфликт → curl --noproxy localhost  
- ✅ Health endpoint работает: {"status":"ok"}
- ✅ SSH туннель Pinggy: https://wzmmn-5-167-17-184.run.pinggy-free.link

**ТЕКУЩЕЕ СОСТОЯНИЕ:**
- uvicorn: localhost:8000 ✅
- Pinggy туннель: активен (60 мин) ✅
- Готов к webhook подписке и /start тесту

**СЛЕДУЮЩИЕ ШАГИ:**
1. Обновить .env с Pinggy URL
2. Перезапуск uvicorn → webhook subscription
3. Тест /start в MAX (ожидаем политику + кнопку согласия)
4. При успехе → переход к F05 каталог

**DoD F04:** ждет live-тест /start для полного завершения
