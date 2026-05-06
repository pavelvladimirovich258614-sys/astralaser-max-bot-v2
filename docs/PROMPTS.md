# PROMPT PLAYBOOK — astralaser-max-bot v2.0

> **Это твой главный рабочий документ.** Открывай его, иди по промптам строго по порядку. Каждый промпт — это одно сообщение, которое ты копируешь и вставляешь агенту (Codex/Kimi/GLM/DeepSeek/Claude Code).

## Как пользоваться

Каждый блок имеет формат:

```
### Промпт №X — [название]
**Кому:** [ты, агент, или оба]
**Когда:** [условия запуска]
**Действие:** [что делаешь]
```

---

## Промпт №0 — Подготовка локально (выполняешь ты, без агента)

**Кому:** ты, в терминале
**Когда:** перед началом работы

```powershell
# 1. Перейди в нужную папку
cd D:\KLIENT_Zakazi\

# 2. Создай новую папку проекта
mkdir astralaser-max-bot-v2
cd astralaser-max-bot-v2

# 3. Инициализируй git
git init

# 4. Создай новый репозиторий на GitHub:
#    https://github.com/new
#    name: astralaser-max-bot-v2
#    private (или public — на твой выбор)

# 5. Привяжи origin (замени URL на свой)
git remote add origin https://github.com/pavelvladimirovich258614-sys/astralaser-max-bot-v2.git
git branch -M main

# 6. Создай Python виртуальное окружение
python -m venv venv
.\venv\Scripts\Activate.ps1

# 7. Скопируй ВСЕ файлы из стартового пакета в эту папку:
#    - AGENTS.md → корень
#    - CLAUDE.md → корень
#    - feature_list.json → корень
#    - progress.md → корень
#    - .env.example → корень (НЕ переименовывай!)
#    - TECHNICAL_SPECIFICATION.md → docs/TZ.md  (создай папку docs)
#    - PROMPT_PLAYBOOK.md → docs/PROMPTS.md
#    - SESSION_HANDOFF.md → docs/HANDOFF.md
#    - seed_products.json → data/seed_products.json (создай папку data)

# 8. Скопируй .env.example → .env и заполни реальными значениями
copy .env.example .env
# Открой .env в редакторе, впиши:
#   - MAX_BOT_TOKEN= (получи у @business_bot)
#   - WEBHOOK_URL= (например, ngrok URL для теста)
#   - MAX_ADMIN_USER_IDS=4147438,73412011

# 9. Создай .gitignore
@'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
env/

# Distribution
build/
dist/
*.egg-info/

# Tests
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/

# Environment
.env
.env.local

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Project
data/photos/  # локальный кеш фото (если будет)
logs/
'@ | Out-File -FilePath .gitignore -Encoding UTF8

# 10. Первый коммит
git add .gitignore AGENTS.md CLAUDE.md feature_list.json progress.md docs/ data/ .env.example
git commit -m "chore: initial project skeleton with TZ, AGENTS, prompts"
git push -u origin main
```

**Чек после №0:**
- [ ] Репозиторий создан на GitHub
- [ ] Локальная папка с файлами стартового пакета
- [ ] `.env` заполнен (не пушится в git)
- [ ] Первый коммит запушен
- [ ] venv активен, Python 3.11

---

## Промпт №1 — Открытие сессии с агентом

**Кому:** агенту (Codex/Kimi/GLM/DeepSeek/Claude Code)
**Когда:** первое сообщение агенту в любой сессии

```markdown
Привет. Ты — со-инженер проекта astralaser-max-bot v2.0. Это бот-магазин украшений с гравировкой для мессенджера MAX (платформа https://max.ru, НЕ Telegram).

Перед написанием любого кода выполни следующее:

1. Прочитай AGENTS.md (или CLAUDE.md, если ты Claude Code) в корне репозитория.
2. Прочитай docs/TZ.md — полное техническое задание.
3. Прочитай feature_list.json — реестр фич.
4. Прочитай последний Session Record в progress.md — текущее состояние.

После этого ответь мне на 4 вопроса:
1. Какая фича сейчас in_progress?
2. Что было сделано в последней сессии (если что-то было)?
3. Какой Next best action согласно progress.md?
4. Есть ли блокеры?

Не пиши код. Не предлагай новые фичи. Не делай рефакторинг. Жди моей следующей команды.
```

**Если агент не имеет доступа к файлам** (например, AnythingLLM без RAG):

```powershell
# Скопируй все 4 файла в буфер:
Get-Content AGENTS.md, docs/TZ.md, feature_list.json, progress.md | Set-Clipboard
```

И вставь в чат с агентом перед промптом №1, обернув разделителями `═══ FILE: AGENTS.md ═══` и т.д.

---

## Промпт №2 — F00 Инфраструктура и harness

**Кому:** агенту
**Когда:** после ответа агента на Промпт №1

```markdown
Открываем фичу **F00 — Инфраструктура и harness**.

Шаг 1: Обнови feature_list.json — переведи F00 в "in_progress".
Шаг 2: Создай следующие файлы в корне репозитория:

### pyproject.toml

```toml
[project]
name = "astralaser-max-bot"
version = "2.0.0"
description = "MAX messenger shop bot for engraved jewelry"
requires-python = ">=3.11"

[tool.ruff]
line-length = 110
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "ASYNC"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.27.1
httpx==0.27.0
sqlalchemy[asyncio]==2.0.27
aiosqlite==0.19.0
asyncpg==0.29.0
alembic==1.13.1
pydantic==2.6.1
pydantic-settings==2.1.0
python-dotenv==1.0.1

pytest==8.0.0
pytest-asyncio==0.23.5
pytest-cov==4.1.0
ruff==0.2.1
mypy==1.8.0
```

### Структура папок

Создай пустые `__init__.py` в:
- `src/`
- `src/bot/`
- `src/bot/handlers/`
- `src/services/`
- `src/db/`
- `src/db/crud/`
- `tests/`
- `scripts/`

### init.ps1 (Windows проверка)

```powershell
Write-Host "=== HARNESS INIT (Astralaser v2) ==="
Write-Host "Working dir: $PWD"

Write-Host "`n[1/4] Architecture checks..."
$slot1 = Select-String -Path "src/bot/handlers/*.py" -Pattern "from src.db.crud" -List
if ($slot1) { Write-Host "VIOLATION: handlers import crud directly!" -ForegroundColor Red; exit 1 }
Write-Host "Architecture: OK"

Write-Host "`n[2/4] Running tests..."
python -m pytest -v --tb=short
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n[3/4] Lint..."
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n[4/4] Type check..."
python -m mypy src/
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n=== READY ===" -ForegroundColor Green
```

### init.sh (Linux версия)

То же самое, только bash-синтаксис.

### Базовый src/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    max_bot_token: str
    max_api_base_url: str = "https://platform-api.max.ru"
    webhook_url: str = ""
    app_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./astralaser.db"
    max_admin_user_ids: str = ""
    manager_name: str = "Менеджер"
    manager_phone: str = ""
    manager_vk_link: str = ""
    max_manager_link: str = ""
    max_required_channel: str = ""
    max_required_channel_url: str = ""
    log_level: str = "INFO"
    http_timeout: int = 30
    working_hours: str = "пн–сб 10:00–18:00 МСК"

    @property
    def admin_ids_list(self) -> list[str]:
        return [x.strip() for x in self.max_admin_user_ids.split(",") if x.strip()]

def get_settings() -> Settings:
    return Settings()
```

### Минимальный тест tests/test_config.py

```python
from src.config import Settings

def test_settings_load_with_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")
    s = Settings()
    assert s.max_bot_token == "test_token"
    assert s.max_api_base_url == "https://platform-api.max.ru"

def test_admin_ids_parsing(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "t")
    monkeypatch.setenv("MAX_ADMIN_USER_IDS", "111,222 , 333")
    s = Settings()
    assert s.admin_ids_list == ["111", "222", "333"]
```

### Шаг 3: проверка

Запусти:
```
python -m pytest -v
python -m ruff check .
python -m mypy src/
.\init.ps1
```

Все 4 команды должны быть зелёные. Пришли мне полный вывод каждой команды.

### Шаг 4: НЕ обновляй feature_list.json в completed.

После прохождения всех проверок останови работу и запиши Session Record в progress.md по формату из AGENTS.md п. 6. Я сам переведу F00 в completed и сделаю финальный коммит.

Запреты:
- Не создавай файлы, которых нет в этом промпте.
- Не пиши код будущих фич (моделей БД, handlers и т.п.) — это будет в следующих промптах.
- Не трогай AGENTS.md, CLAUDE.md, docs/TZ.md.
```

**После ответа агента (твоё действие):**
1. Проверь вывод `pytest`, `ruff`, `mypy`, `init.ps1`
2. Если всё зелёное — открой `feature_list.json`, переведи F00 в `completed`, добавь `completed_at` и `evidence`
3. Сделай коммит: `git commit -am "feat(F00): infrastructure and harness setup"`
4. Push: `git push origin main`
5. Переходи к Промпту №3

---

## Промпт №3 — F01 БД, модели, миграции, seed

**Кому:** агенту
**Когда:** после закрытия F00

```markdown
F00 закрыта. Открываем фичу **F01 — БД, модели, миграции, seed**.

Шаг 1: Обнови feature_list.json — переведи F01 в "in_progress".

Шаг 2: Создай файлы по порядку:

### src/db/engine.py

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from src.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```

### src/db/models.py

Создай 8 моделей по docs/TZ.md раздел 3.F01:
- User (id, max_user_id UNIQUE, username, full_name, consent_at, created_at)
- Category (id, title, slug UNIQUE, description, sort_order, is_active, created_at)
- Product (id, category_id FK, title, description, price, cover_url, is_active, sort_order, created_at)
- ProductPhoto (id, product_id FK cascade, url, sort_order)
- CartItem (id, user_id FK, product_id FK, quantity, created_at, UNIQUE(user_id, product_id))
- Order (id, user_id FK, customer_name, customer_phone, delivery_address, total_amount, status, notes, created_at, updated_at)
- OrderItem (id, order_id FK cascade, product_id FK, product_title_snapshot, price_snapshot, quantity)
- UserState (user_id PK FK, state, data JSON-string, updated_at)

Используй SQLAlchemy 2.x style: `Mapped[]`, `mapped_column()`, `DeclarativeBase`.

### Alembic init

```bash
python -m alembic init alembic
```

Затем поправь `alembic/env.py` чтобы он использовал async engine из `src/db/engine.py` и подхватывал metadata из `src/db/models.py`.

Создай initial миграцию:
```bash
python -m alembic revision --autogenerate -m "initial schema"
python -m alembic upgrade head
```

### src/db/crud/ — 7 файлов

Каждый CRUD-модуль (user.py, category.py, product.py, product_photo.py, cart.py, order.py, user_state.py) должен экспортировать async функции с типизацией.

Минимум на старт:
- `user.py`: get_user_by_max_id, create_user, update_consent
- `category.py`: get_active_categories, get_by_slug
- `product.py`: get_by_id, get_by_category, get_active_only
- `product_photo.py`: get_by_product_id (sorted by sort_order)
- `cart.py`: add_item, remove_item, get_user_cart, clear_cart, update_quantity
- `order.py`: create_order, get_by_id, get_by_user, list_by_status, update_status
- `user_state.py`: get_state, set_state, clear_state

### scripts/seed_db.py

Идемпотентный seed. Читает `data/seed_products.json`, создаёт категории/товары/фото только если их нет.

```python
import asyncio
import json
from pathlib import Path
from sqlalchemy import select
from src.db.engine import async_session_maker
from src.db.models import Category, Product, ProductPhoto

SEED_FILE = Path(__file__).parent.parent / "data" / "seed_products.json"

async def seed():
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    async with async_session_maker() as session:
        new_products_total = 0
        for cat_data in data["categories"]:
            # Получи или создай категорию (по slug)
            # Для каждого товара: если нет (по title+category_id) — создай Product + все ProductPhoto
            # Подсчитай new_products
            ...
        await session.commit()
        print(f"Seed complete: new_products_total={new_products_total}")

if __name__ == "__main__":
    asyncio.run(seed())
```

Реализуй полностью, идемпотентно. После повторного запуска должен выводить `new_products_total=0`.

### tests/test_models.py

Минимум 5 тестов:
- Все 8 таблиц в metadata
- Product имеет нужные колонки
- ProductPhoto cascade при удалении Product
- CartItem unique(user_id, product_id)
- UserState имеет state и data

Используй in-memory SQLite + StaticPool для тестов.

### tests/test_crud.py

Минимум 8 тестов на основные CRUD-функции (user create/get, category get_by_slug, product get_by_category, cart add/remove, order create, user_state set/get/clear).

### Шаг 3: проверка

```
python -m alembic upgrade head
python scripts/seed_db.py
python scripts/seed_db.py  # второй запуск, должно быть new_products_total=0
python -m pytest -v
python -m ruff check .
python -m mypy src/
.\init.ps1
```

Все команды должны быть зелёные.

### Шаг 4: Session Record

После прохождения всех проверок:
- НЕ обновляй feature_list.json в completed.
- Запиши Session Record в progress.md.
- Жди моей команды.

Запреты:
- Не создавай handlers, max_client, webhook — это следующие фичи.
- Не пиши test_handlers.py — мы ещё не дошли.
- Не трогай конфиг или env.
```

**После ответа агента:**
1. Проверь все 4 проверки
2. Открой `data/astralaser.db` (sqlite browser) — убедись, что 3 категории и 4 товара
3. Если всё ок — переведи F01 в `completed`, коммить
4. Переходи к Промпту №4

---

## Промпт №4 — F02 Транспорт MAX API

**Кому:** агенту
**Когда:** после закрытия F01

```markdown
F01 закрыта. Открываем фичу **F02 — Транспорт MAX API (max_client.py)**.

Шаг 1: Обнови feature_list.json — F02 в "in_progress".

Шаг 2: Реализуй src/bot/max_client.py:

```python
from __future__ import annotations
import logging
from typing import Any
import httpx
from src.config import get_settings

logger = logging.getLogger(__name__)


class MAXClient:
    """HTTP клиент MAX API. Использует Authorization header (НЕ access_token в URL)."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        settings = get_settings()
        self._token = token or settings.max_bot_token
        self._base_url = (base_url or settings.max_api_base_url).rstrip("/")
        if not self._token:
            raise RuntimeError("MAX_BOT_TOKEN must be set")

        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": self._token},
            timeout=settings.http_timeout,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "MAXClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # ---- helpers ----

    @staticmethod
    def _build_inline_keyboard(buttons: list[list[dict]]) -> dict:
        """buttons = [[{"text": "...", "callback_data": "..."}], ...]"""
        return {
            "type": "inline_keyboard",
            "payload": {"buttons": buttons},
        }

    def _build_payload(
        self, text: str, reply_markup: list[list[dict]] | None, photo_url: str | None
    ) -> dict[str, Any]:
        attachments: list[dict] = []
        if photo_url:
            attachments.append({"type": "image", "payload": {"url": photo_url}})
        if reply_markup:
            attachments.append(self._build_inline_keyboard(reply_markup))

        payload: dict[str, Any] = {"text": text}
        if attachments:
            payload["attachments"] = attachments
        return payload

    # ---- methods ----

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: list[list[dict]] | None = None,
        photo_url: str | None = None,
    ) -> dict[str, Any]:
        try:
            r = await self._client.post(
                "/messages",
                params={"chat_id": chat_id},
                json=self._build_payload(text, reply_markup, photo_url),
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.warning("send_message failed: status=%s body=%s", e.response.status_code, e.response.text)
            return {}

    async def edit_message(
        self,
        chat_id: int | str,
        message_id: str,
        text: str,
        reply_markup: list[list[dict]] | None = None,
        photo_url: str | None = None,
    ) -> dict[str, Any]:
        try:
            r = await self._client.patch(
                f"/messages/{message_id}",
                params={"chat_id": chat_id},
                json=self._build_payload(text, reply_markup, photo_url),
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.warning("edit_message failed: status=%s body=%s", e.response.status_code, e.response.text)
            return {}

    async def delete_message(self, chat_id: int | str, message_id: str) -> bool:
        try:
            r = await self._client.delete(
                f"/messages/{message_id}",
                params={"chat_id": chat_id},
            )
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("delete_message failed: status=%s", e.response.status_code)
            return False

    async def answer_callback_query(self, callback_id: str, notification: str | None = None) -> bool:
        try:
            payload = {"notification": notification} if notification else {}
            r = await self._client.post(
                "/answers",
                params={"callback_id": callback_id},
                json=payload,
            )
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("answer_callback_query failed: status=%s", e.response.status_code)
            return False

    async def subscribe_webhook(self, url: str) -> bool:
        try:
            r = await self._client.post("/subscriptions", json={"url": url})
            r.raise_for_status()
            logger.info("Webhook subscribed: %s", url)
            return True
        except httpx.HTTPStatusError as e:
            logger.error("subscribe_webhook failed: status=%s body=%s", e.response.status_code, e.response.text)
            return False

    async def unsubscribe_webhook(self, url: str) -> bool:
        try:
            r = await self._client.delete("/subscriptions", params={"url": url})
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False

    async def get_chat_member(self, chat_id: int | str, user_id: int | str) -> dict | None:
        try:
            r = await self._client.get(f"/chats/{chat_id}/members/{user_id}")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError:
            return None
```

### tests/test_max_client.py

Используй `httpx.MockTransport` для всех тестов. Покрой:

1. Authorization header установлен в self._client.headers
2. send_message формирует правильный payload (text, attachments с image и keyboard)
3. send_message при 4xx логирует warning и возвращает {}
4. edit_message делает PATCH /messages/{id}
5. delete_message делает DELETE
6. answer_callback_query делает POST /answers
7. subscribe_webhook делает POST /subscriptions
8. get_chat_member возвращает None при 404

Минимум 8 тестов.

### Шаг 3: проверка

```
python -m pytest -v
python -m ruff check .
python -m mypy src/
.\init.ps1
```

### Шаг 4: Session Record и стоп.

Запреты:
- Не создавай webhook endpoint — это F03.
- Не создавай router или handlers — это позже.
- Не пиши uvicorn — это F03.
```

**После закрытия F02 — Промпт №5.**

---

> ⚠️ **Этот плейбук состоит из двух частей.** Промпты F03–F12 — в файле `PROMPT_PLAYBOOK_PART2.md`. Открой его после закрытия F02.

