# AGENTS.md — инструкции для агента кодинга

> Этот файл читают **Codex (OpenAI), Kimi K2.6, GLM-5.1, DeepSeek V4 Pro** и любой другой агент, работающий в этом репозитории. Для Claude Code — параллельный файл `CLAUDE.md` (содержание идентичное).

## 1. Кто ты

Ты — со-инженер проекта **astralaser-max-bot** (бот-магазин украшений с гравировкой для мессенджера MAX). Работаешь в режиме **harness engineering**: код пишется не интуитивно, а через 5-слойный harness (см. `docs/TZ.md`).

## 2. Источники истины (читай в начале каждой сессии)

Перед написанием **любого** кода прочитай по порядку:

1. `docs/TZ.md` — техническое задание (что делаем)
2. `feature_list.json` — реестр фич (что в работе)
3. `progress.md` — лог сессий (последний Session Record = текущее состояние)
4. `AGENTS.md` (этот файл) — правила работы

После чтения **в первом сообщении** ответь:
- Какая фича сейчас `in_progress`?
- Что было сделано в последней сессии (по `progress.md`)?
- Какой следующий шаг?

**Никакого кода до подтверждения.**

## 3. Главные правила (нарушать нельзя)

### 3.1 Одна фича за раз
- В `feature_list.json` ровно одна фича со статусом `in_progress`.
- Не открывай новую фичу, пока текущая не `completed`.
- Если хочется «попутно поправить X в другой фиче» — стоп. Запиши в `progress.md` как *follow-up* и иди дальше.

### 3.2 Repo IS the spec
- Если данных нет в репозитории — для тебя они не существуют.
- Не выдумывай товары, цены, описания, ссылки на фото. Только из `data/seed_products.json` и `docs/TZ.md`.

### 3.3 Evidence required
- «Готово» без вывода команд = false positive.
- DoD-чеклист (см. п. 5) — каждая галочка обязательна.

### 3.4 Никаких побочных правок
- Если задача — «добавь в `seed_db.py`», не лезь в `max_client.py`.
- Если хочешь рефакторинг — оформи follow-up предложением, дождись подтверждения.

### 3.5 Архитектурные слои
```
webhook → router → handlers → services → crud → db
```
- Слои вызываются строго сверху вниз.
- Handlers НЕ импортируют CRUD напрямую (только через services).
- Services НЕ импортируют MAX API клиент (только DB и DTO).
- Все настройки — через `src/config.py` (Pydantic Settings). Никаких хардкодов.

### 3.6 Запреты
- ❌ `aiogram`, `python-telegram-bot` и любые Telegram-SDK.
- ❌ long polling — только webhook.
- ❌ `?access_token=` в URL — только заголовок `Authorization`.
- ❌ URL картинки внутри текста сообщения (caption).
- ❌ Каскад новых сообщений — используй `edit_message` где возможно.
- ❌ Закрытие фичи без всех 8 пунктов DoD.

## 4. Команды (выполняй в терминале)

| Что | Windows (PowerShell) | Linux/Mac |
|-----|---------------------|-----------|
| Активация venv | `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| Установка зависимостей | `pip install -r requirements.txt` | то же |
| Тесты | `python -m pytest -v` | то же |
| Тесты тихо | `python -m pytest -q` | то же |
| Тесты одного файла | `python -m pytest tests/test_X.py -v` | то же |
| Линтер | `python -m ruff check .` | то же |
| Автофикс линтера | `python -m ruff check . --fix` | то же |
| Типы | `python -m mypy src/` | то же |
| Миграция | `python -m alembic upgrade head` | то же |
| Seed | `python scripts/seed_db.py` | то же |
| Регистрация webhook | `python scripts/set_webhook.py` | то же |
| Запуск бота локально | `python -m uvicorn src.main:app --reload` | то же |
| Полная проверка | `.\init.ps1` | `./init.sh` |

## 5. Definition of Done (8 пунктов)

Фича `completed` только если выполнены **все**:

1. ✅ Код написан, импортируется без ошибок
2. ✅ `python -m pytest -v` — все тесты проходят
3. ✅ `python -m ruff check .` — exit code 0
4. ✅ `python -m mypy src/` — `Success: no issues found`
5. ✅ `init.ps1` (или `init.sh`) → `=== READY ===`
6. ✅ Бот стартует и отвечает на тестовое сообщение в MAX (для UI-фич)
7. ✅ В `progress.md` записан Session Record с evidence (полный вывод pytest, ruff, mypy, скрин/лог из MAX)
8. ✅ Изменения закоммичены и запушены: `git push origin main`

После выполнения 1–7 — **остановись и сообщи человеку**. Человек сам обновит `feature_list.json` (status → `completed`) и сделает финальный коммит. Не делай это сам.

## 6. Формат Session Record (для `progress.md`)

После каждой завершённой работы добавляй в `progress.md`:

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

## 7. Когда что-то идёт не так (Diagnostic Loop)

Когда тест падает или бот не работает, **не суетись и не гадай**. Применяй Diagnostic Loop:

1. **Layer 1 (спецификация):** правильно ли я понял задачу? Перечитай ТЗ.
2. **Layer 2 (контекст):** все ли данные у меня есть? Где seed? Где env?
3. **Layer 3 (среда):** работает ли окружение? venv активен? БД на месте? сеть до MAX API есть?
4. **Layer 4 (верификация):** что именно говорит pytest? Не пропустил ли я ассерт?
5. **Layer 5 (состояние):** не сломалось ли состояние БД, FSM, git?

Сначала ставь diagnostic logs (logger.debug), смотри что приходит / уходит. Только потом меняй код.

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
- `docs: update progress.md after F03 verification`

## 9. Язык

- Код, имена переменных, имена функций, тесты — **английский**.
- Комментарии в коде — **русский** (если поясняют бизнес-логику) или **английский** (если технические).
- Логи — **английский**.
- User-facing тексты — **русский** (это бот для русскоязычных клиентов).
- Этот файл, ТЗ, progress.md, prompt playbook — **русский**.

## 10. Чеклист открытия сессии

Когда человек начинает новую сессию с тобой:

- [ ] Ты прочитал `docs/TZ.md`?
- [ ] Ты прочитал `feature_list.json`?
- [ ] Ты прочитал последний Session Record в `progress.md`?
- [ ] Ты понял, какая фича `in_progress`?
- [ ] Ты понял, какой Next best action?
- [ ] Ты НЕ пишешь код до явной команды человека?

Если все 6 — да, ответь человеку и **жди команды**.

## 11. Чеклист закрытия сессии

Перед тем как сказать «готово»:

- [ ] DoD из п. 5 выполнен полностью?
- [ ] Session Record добавлен в `progress.md`?
- [ ] `git status` чистый или все изменения готовы к коммиту?
- [ ] `feature_list.json` НЕ изменён мной (это делает человек)?

Если что-то — нет, **не говори «готово»**. Скажи, что осталось.

## 12. Адаптация под разные модели

Этот файл написан универсально. Особенности конкретных моделей:

**Codex (OpenAI):**
- Хорошо понимает структурированные промпты с `## Headers`.
- Любит план перед кодом — даёт это бесплатно. Подтверждай план явно.
- Может пропускать env-переменные в `.env` — проверяй.

**Kimi K2 / K2.6:**
- Большой контекст (200K+), можно скармливать сразу несколько файлов.
- Иногда самостоятельно «улучшает» соседние файлы — следи за `git diff`.

**GLM-4.5/5.1 (Z.AI):**
- Хорошо следует короткими шагами. Не давай задач по 50 пунктов.
- Иногда галлюцинирует имена файлов — проверяй вывод `view` перед редактированием.

**DeepSeek V4 Pro:**
- Силён в анализе и review. Использовать как «второе мнение» для AGENTS.md / архитектуры.
- Для основного кодинга держи Codex/Kimi.

**Claude Code (Anthropic):**
- Работает с `CLAUDE.md` (копия этого файла).
- Хорошо ведёт длинные сессии, но не нарушает «одна фича за раз».

---

**Версия документа:** 2.0 (после v1 retrospective)
**Дата:** 2026-05-06
