# NEXT_SESSION_PROMPT (2026-05-16 hand-off)

Ты Codex-CLI исполнитель, я навигатор. Сначала прочитай `AGENTS.md`, `feature_list.json`, последний Session Record в `progress.md`, затем этот hand-off.

## Current verified state

- Production path: `/opt/astralaser-max-bot-v2`.
- Main menu UI is stable and deployed.
- F13 Priority Mini App inline `open_app` button is `removed`: live MAX clients rendered it visually, but PC loaded forever and mobile did not respond.
- Current Mini App strategy: greeting CAPS text + delayed visual instruction image + the native MAX system Mini App button in the lower-left corner.
- F15 marketplace links are `completed`: bottom row has `📦 Ozon` and `🟣 Wildberries`.
- MAX marketplace button type must be `link`, not `url`; production MAX API rejected `type=url` with `proto.payload`.
- F16 delayed visual instruction is `completed`: consented `/start` sends menu immediately, waits 10 seconds with `asyncio.sleep(10)`, sends the image instruction, and `instruction:close` deletes that message.
- `src/bot/webhook.py` mypy blocker is resolved. Harness is clean: pytest 318 passed, ruff clean, mypy clean, local `init.ps1` READY, server `init.sh` READY.

## Next best action

No feature is currently `in_progress`. Wait for the next explicit task from the user.

## Guardrails

- Do not reintroduce inline `open_app` in the main menu unless the user explicitly asks for a new MAX Bridge investigation.
- Do not change marketplace buttons from `type=link` to `type=url`.
- Keep user-facing Mini App guidance in Russian and uppercase where requested, because MAX rendered markdown `**` literally.
