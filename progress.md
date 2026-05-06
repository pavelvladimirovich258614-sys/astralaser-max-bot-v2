# Progress Log — astralaser-max-bot v2.0

> Источник истины №3. Лог сессий проекта. Каждый агент в начале сессии читает последний Session Record, в конце — добавляет новый.

## Current Verified State

**Статус проекта:** F00 implemented → awaiting human verification
**Текущая фича `in_progress`:** F00 — Инфраструктура и harness
**Следующая фича по дорожной карте:** F01 — БД, модели, миграции, seed
**Последний коммит:** `<awaiting human commit>`
**Тесты:** 2 passed

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

**Это Progress Log v2.** v1 архивирован в Git history старого репозитория.
