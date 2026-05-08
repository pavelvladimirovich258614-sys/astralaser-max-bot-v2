# NEXT_SESSION_PROMPT (2026-05-09 → 2026-05-10)

Ты Codex-CLI исполнитель, я навигатор. Узкие промпты, стоп-правила, TDD, без коммитов без моей команды, всегда сначала diff + план словами.

## Прочитать в порядке
1. NEXT_SESSION_PROMPT.md (этот файл)
2. progress.md — Session Record 2026-05-09
3. AGENTS.md
4. feature_list.json (F05 in_progress, F06 todo)
5. docs/TZ.md разделы 2.2 (attachments/upload) и edit-message
6. src/bot/handlers/catalog.py (show_product_card)
7. src/bot/max_client.py (_build_payload, edit_message)
8. src/services/catalog_service.py (get_product_card)

## Текущее состояние
- F05 каталог почти готов, остался один баг: серое пустое фото при PUT /messages в карточках.
- 58 тестов зелёные, ruff чисто, mypy 1 known warning.
- 2 коммита впереди origin/main, push отложен.

## Твой первый ответ
- "ок, вник" + 3-5 строк состояния.
- Дождись моей команды на эксперимент 1.

## Эксперимент 1 (по моей команде)
Скилл: incremental-implementation + tdd.

Минимальное изменение в src/bot/handlers/catalog.py:
- В show_product_card временно вызывать edit_message только с photo_url=card.photo_url, photo=None, независимо от наличия токена.
- Не трогать БД, не трогать seed, не трогать max_client.

Шаги:
1. Diff + план словами, ждать approve.
2. После approve: внести изменение, обновить/добавить тест в tests/test_catalog.py (карточка использует photo_url, не token).
3. pytest -v, ruff check ., mypy src — выложить вывод.
4. Жди мою команду на uvicorn restart и live-test.
5. После live-test:
   - Фото появилось → гипотеза 1 подтверждена. Жди промпта на финальную правку (photo_url как основной путь, token как опциональный fallback) + закрытие F05.
   - Серый блок остался → откатить изменение, доложить, ждать промпта на эксперимент 2.

## Стоп-правила
- Не править scripts/seed_db.py, src/services/max_upload_service.py, БД, миграции.
- Не делать новый upload фото.
- Не коммитить и не пушить без моей команды.
- Не редактировать progress.md и feature_list.json до закрытия F05.

## Утренний чеклист навигатора
1. Терминал 1: python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 — ждать "Webhook subscribed".
2. Терминал 2: ssh -R 8090:127.0.0.1:8080 root@82.26.151.81.
3. Happ VPN в Proxy.
4. Отправить Kimi стартовое сообщение, дождаться "ок, вник".
5. Дать команду на эксперимент 1.
