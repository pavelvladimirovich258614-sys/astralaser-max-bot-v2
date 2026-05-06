# 🚀 Astralaser MAX Bot — стартовый пакет (v2.0)

Это полный набор документов для перезапуска проекта **astralaser-max-bot** с нуля под мессенджер MAX.

## Что внутри пакета

| Файл | Куда копировать в репозитории | Зачем нужен |
|------|------------------------------|-------------|
| `TECHNICAL_SPECIFICATION.md` | `docs/TZ.md` | Полное техническое задание (источник истины №1) |
| `AGENTS.md` | `AGENTS.md` (корень) | Инструкции для Codex / Kimi / DeepSeek |
| `CLAUDE.md` | `CLAUDE.md` (корень) | Инструкции для Claude Code (копия AGENTS.md) |
| `PROMPT_PLAYBOOK.md` | `docs/PROMPTS.md` | Пошаговые промпты для всего проекта (твой главный файл) |
| `feature_list.json` | `feature_list.json` (корень) | Реестр фич (источник истины №2) |
| `progress.md` | `progress.md` (корень) | Лог сессий (источник истины №3) |
| `SESSION_HANDOFF.md` | `docs/HANDOFF.md` | Как передавать проект между агентами |
| `.env.example` | `.env.example` (корень) | Шаблон переменных окружения |
| `seed_products.json` | `data/seed_products.json` | Данные всех товаров для seed |
| `README.md` | `README.md` (корень) | Быстрый старт для людей |

## Порядок действий (общая картина)

1. **Создай новый чистый репозиторий** на GitHub: `astralaser-max-bot-v2`
2. **Скопируй все файлы из этого пакета** в нужные места (см. таблицу выше)
3. **Заполни `.env`** реальными значениями (токен MAX, домен webhook, админ ID)
4. **Открой `PROMPT_PLAYBOOK.md`** — там пошагово все промпты для агента
5. **Иди по промптам строго по порядку**, не перескакивая
6. **После каждой фичи** — проверяй DoD (Definition of Done) и обновляй `progress.md`

## Главное правило (нарушать нельзя)

**Одна фича со статусом `in_progress` за раз.**
Не открывай F02, пока F01 не закрыта. Не открывай F03, пока F02 не закрыта.
Если агент пытается прыгнуть вперёд — останавливай и возвращай к текущей фиче.

## Главное доказательство (Definition of Done)

Фича считается `completed` только если:
- ✅ Код написан и закоммичен
- ✅ Тесты проходят (`pytest -v`)
- ✅ Линтер чистый (`ruff check .`)
- ✅ Типы чистые (`mypy src/`)
- ✅ Bot стартует без ошибок (если применимо к фиче)
- ✅ В `progress.md` записан Session Record с evidence

Без всех 6 пунктов — фича остаётся `in_progress`.

## Ключевые отличия от v1

В прошлой версии проекта мы наступили на следующие грабли — в v2 они исправлены:

1. **Webhook вместо long polling.** MAX API с 11.05.2026 урезает polling до 2 RPS / 30s timeout. С самого начала пишем на webhook (FastAPI + nginx + Let's Encrypt).
2. **Authorization header с самого начала.** Никаких `access_token` в URL.
3. **Подмена сообщений (edit_message)** во всех handlers, чтобы не было свалки в чате.
4. **Политика конфиденциальности первым сообщением** при `/start` — пока пользователь не примет, дальше не пускаем.
5. **Админ-панель встроена** — добавление товаров без правки кода.
6. **Проверка подписки на канал** — отдельная финальная фича.
7. **Категории: Колье и кулоны, Браслеты, Брелоки** — все три с самого начала, не добавляем по одному.

## Стек (фиксируем сразу)

- Python 3.11
- aiohttp + FastAPI (webhook)
- SQLAlchemy 2.x async + Alembic
- SQLite (dev) → PostgreSQL (prod) через `DATABASE_URL`
- httpx (для запросов к MAX API)
- Pydantic Settings (конфиг)
- pytest + pytest-asyncio (тесты)
- ruff + mypy (качество)
- nginx + systemd + Let's Encrypt (деплой)

## Документация MAX (закрепи в браузере)

- API: <https://dev.max.ru/docs-api>
- Webhook subscriptions: <https://dev.max.ru/docs-api/methods/POST/subscriptions>
- WebApps: <https://dev.max.ru/docs/webapps/introduction>
- Поддержка: partner_support@max.ru / `@business_bot`

---

**Дальше — открой `PROMPT_PLAYBOOK.md` и начинай с Промпта №0.**
