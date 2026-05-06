# Progress Log — astralaser-max-bot v2.0

> Источник истины №3. Лог сессий проекта. Каждый агент в начале сессии читает последний Session Record, в конце — добавляет новый.

## Current Verified State

**Статус проекта:** initialized
**Текущая фича `in_progress`:** нет
**Следующая фича по дорожной карте:** F00 — Инфраструктура и harness
**Последний коммит:** `<пусто>`
**Тесты:** `<пусто>`

---

## Session Record — 2026-XX-XX HH:MM (TEMPLATE)

> Удали этот блок-шаблон и используй формат ниже для реальных записей.

**Agent:** Codex / Kimi K2 / GLM-5.1 / DeepSeek V4 Pro / Claude Code
**Feature:** F0X-feature-name
**Status:** `started` / `implemented` / `awaiting verification` / `completed`

### What was done

- ...

### Evidence

```
$ python -m pytest -v
... passed in Xs

$ python -m ruff check .
exit code 0

$ python -m mypy src/
Success: no issues found in N source files

$ .\init.ps1
=== READY ===
```

### Live test in MAX (если применимо)

- `/start` → ✅ работает / ❌ проблема: ...
- Скриншот: `<ссылка или N/A>`

### Notes / follow-ups

- ...

### Next best action

- ...

### Commit

```
<sha> <commit message>
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
