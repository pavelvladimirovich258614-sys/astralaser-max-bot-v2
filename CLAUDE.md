# AGENTS.md — инструкции для агента кодинга

> Этот файл читают Codex, Kimi K2.6, GLM-5.1, DeepSeek V4 Pro и любой другой агент. Для Claude Code — параллельный файл `CLAUDE.md` (содержание идентичное).

## 1. Кто ты

Со-инженер проекта **astralaser-max-bot** (бот-магазин украшений с гравировкой для мессенджера MAX). Код пишется через 5-слойный harness (см. `docs/TZ.md`).

## 2. Источники истины (читай перед кодом)

1. `docs/TZ.md` — техническое задание
2. `feature_list.json` — реестр фич (только один `in_progress`)
3. `progress.md` — лог сессий (последний Session Record = текущее состояние)
4. `AGENTS.md` — этот файл

**В первом сообщении ответь:**
- Какая фича сейчас `in_progress`?
- Что было сделано в последней сессии?
- Какой следующий шаг?

**Никакого кода до подтверждения человеком.**

## 3. Главные правила

### 3.1 Одна фича за раз
- В `feature_list.json` ровно одна фича `in_progress`.
- Не открывай новую, пока текущая не `completed`.
- Попутные правки → follow-up в `progress.md`, не в коде.

### 3.2 Repo IS the spec
- Не выдумывай товары, цены, описания, фото. Только `data/seed_products.json` и `docs/TZ.md`.

### 3.3 Никаких побочных правок
- Задача «добавь в `seed_db.py`» ≠ лезь в `max_client.py`.
- Рефакторинг — только после явного approve.

### 3.4 Архитектурные слои (строго)
```
webhook → router → handlers → services → crud → db
```
- Handlers НЕ импортируют CRUD напрямую (только через services).
- Services НЕ импортируют MAX API клиент (только DB и DTO).
- Все настройки — через `src/config.py` (Pydantic Settings). Никаких хардкодов.

### 3.5 Запреты
- ❌ `aiogram`, `python-telegram-bot` и любые Telegram-SDK.
- ❌ long polling — только webhook.
- ❌ `?access_token=` в URL — только заголовок `Authorization`.
- ❌ URL картинки внутри текста сообщения (caption). Картинка — через attachments.
- ❌ Каскад новых сообщений — используй `edit_message` где возможно.
- ❌ Закрытие фичи без всех 8 пунктов DoD.

## 4. Команды и настройки инструментов

| Что | Windows (PowerShell) | Linux/Mac |
|-----|---------------------|-----------|
| Активация venv | `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| Установка зависимостей | `pip install -r requirements.txt` | то же |
| Тесты | `python -m pytest -v` | то же |
| Тесты одного файла | `python -m pytest tests/test_X.py -v` | то же |
| Линтер | `python -m ruff check .` | то же |
| Автофикс линтера | `python -m ruff check . --fix` | то же |
| Типы | `python -m mypy src/` | то же |
| Миграция | `python -m alembic upgrade head` | то же |
| Seed | `python scripts/seed_db.py` | то же |
| Регистрация webhook | `python scripts/set_webhook.py` | то же |
| Запуск локально | `python -m uvicorn src.main:app --reload` | то же |
| Полная проверка | `.\init.ps1` | `./init.sh` |

**Важные настройки из `pyproject.toml` (не менять без причины):**
- Ruff: line-length 110, target py311, select `["E", "F", "I", "N", "W", "UP", "B", "C4", "ASYNC"]`.
- mypy: strict, ignore_missing_imports.
- pytest: asyncio_mode = auto.

**Особенности `init.ps1` / `init.sh`:**
- Помимо pytest, ruff и mypy, скрипт проверяет архитектурные ограничения (например, отсутствие прямого импорта `src.db.crud` из `src/bot/handlers`).

## 5. Definition of Done (8 пунктов)

Фича `completed` только если выполнены **все**:

1. ✅ Код написан, импортируется без ошибок
2. ✅ `python -m pytest -v` — все тесты проходят
3. ✅ `python -m ruff check .` — exit code 0
4. ✅ `python -m mypy src/` — `Success: no issues found`
5. ✅ `.\init.ps1` (или `./init.sh`) → `=== READY ===`
6. ✅ Бот стартует и отвечает на тестовое сообщение в MAX (для UI-фич)
7. ✅ В `progress.md` записан Session Record с evidence (полный вывод pytest, ruff, mypy, скрин/лог из MAX)
8. ✅ Изменения закоммичены и запушены: `git push origin main`

После выполнения 1–7 — **остановись и сообщи человеку**. Человек сам обновит `feature_list.json` (status → `completed`) и сделает финальный коммит. Не делай это сам.

## 6. Session Record (добавлять в `progress.md`)

```markdown
## Session Record — YYYY-MM-DD HH:MM

**Agent:** <Codex / Kimi K2.6 / GLM-5.1 / DeepSeek V4 Pro / Claude Code>
**Feature:** F0X-feature-name
**Status:** implemented → awaiting human verification

**What was done:**
- Файл A: добавлено X
- Файл B: изменено Y
- Тесты: добавлены тесты Z

**Evidence:**
- pytest: 56 passed
- ruff: exit 0
- mypy: clean
- init.ps1: READY
- runtime: <скрин из MAX или N/A>

**Notes / follow-ups:**
- Возможный рефакторинг X (не входит в текущую фичу)

**Next best action:** <что делать в следующей сессии>
```

## 7. Diagnostic Loop (если тест падает или бот молчит)

1. **Спецификация:** правильно ли понял задачу? Перечитай ТЗ.
2. **Контекст:** все ли данные есть? Где seed? Где env?
3. **Среда:** venv активен? БД на месте? Сеть до MAX API есть?
4. **Верификация:** что именно говорит pytest? Не пропустил ли ассерт?
5. **Состояние:** не сломалось ли состояние БД, FSM, git?

Сначала ставь diagnostic logs (`logger.debug`), смотри что приходит / уходит. Только потом меняй код.

## 8. Стиль коммитов

```
<type>: <short summary>

<optional body>

<footer with feature ID>
```

Типы: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `seed`.

Примеры:
- `feat(F05): add catalog category navigation with edit_message`
- `fix(F02): handle 4xx from MAX API gracefully`
- `seed: add brelok category with engraved leather keychain`

## 9. Язык

- Код, имена переменных, функции, тесты — **английский**.
- Комментарии — **русский** (бизнес-логика) или **английский** (техника).
- Логи — **английский**.
- User-facing тексты — **русский**.
- Этот файл, ТЗ, progress.md — **русский**.

## 10. Чеклист открытия сессии

- [ ] Прочитал `docs/TZ.md`?
- [ ] Прочитал `feature_list.json`?
- [ ] Прочитал последний Session Record в `progress.md`?
- [ ] Понял, какая фича `in_progress`?
- [ ] Понял, какой Next best action?
- [ ] НЕ пишу код до явной команды человека?

Если все 6 — да, ответь человеку и **жди команды**.

## 11. Чеклист закрытия сессии

- [ ] DoD из п. 5 выполнен полностью?
- [ ] Session Record добавлен в `progress.md`?
- [ ] `git status` чистый или все изменения готовы к коммиту?
- [ ] `feature_list.json` НЕ изменён мной?

Если что-то — нет, **не говори «готово»**. Скажи, что осталось.

---
**Версия документа:** 2.1
**Дата:** 2026-05-06
