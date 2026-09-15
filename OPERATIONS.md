# Эксплуатация SZ Loto Notifier

Актуально на 14 сентября 2026 года.

## Назначение

Сервис отправляет результаты двух лотерей в Telegram:

- Loto 5/36 — внешний запуск ежедневно в 21:05 Asia/Almaty;
- Loto 6/49 — внешний запуск ежедневно в 22:05 Asia/Almaty;
- если результат ещё не опубликован, GitHub Actions повторяет проверку каждую минуту до трёх часов;
- один тираж не отправляется повторно;
- для 6/49 бонусный шар выводится отдельно.

Ноутбук пользователя не участвует. Цепочка: cron-job.org → GitHub repository_dispatch → GitHub Actions → API результатов → Telegram.

## Настройки cron-job.org

Обе задачи используют:

```text
URL: https://api.github.com/repos/anadyrov/sz-loto-notifier/dispatches
Method: POST
Timezone: Asia/Almaty
Basic HTTP authentication: OFF
Accept: application/vnd.github+json
Authorization: Bearer <FINE_GRAINED_PAT>
Content-Type: application/json
```

Токен GitHub должен иметь доступ только к репозиторию `anadyrov/sz-loto-notifier` и разрешение `Contents: Read and write`.

Задача `Loto_536`:

```text
Schedule: daily 21:05
Body: {"event_type":"loto536"}
```

Задача `Loto_649`:

```text
Schedule: daily 22:05
Body: {"event_type":"loto649"}
```

Успешный тест cron-job.org возвращает `204 No Content`. Это подтверждает только приём события GitHub, но не доставку сообщения. Если cron запускается раньше времени тиража, workflow остаётся активным, ждёт заданного времени и затем опрашивает источник.

## GitHub Actions

Workflow: `.github/workflows/loto.yml` (`Loto 5/36 and 6/49 notifier`).

- `loto536` запускает `python main.py --window --game 536`;
- `loto649` запускает `python main.py --window --game 649`;
- старый `watchdog` сохранён как совместимость и обрабатывается как 5/36;
- ручной `workflow_dispatch` выполняет безопасный `--probe`: проверяет токен Telegram, доступ бота к конкретному `chat_id` и оба источника, но не рассылает результаты;
- `telegramtest` выполняет реальную тестовую отправку;
- `recover536` и `recover649` выполняют разовую восстановительную отправку последних результатов.

GitHub Secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

SMS сейчас принудительно выключены в workflow (`SMS_ENABLED=false`). Состояние сохраняется в GitHub Actions cache раздельно для 5/36 и 6/49.

## Источники результатов

Основные облачно-доступные JSON endpoints:

```text
https://lucky-numbers.ru/api/v1/lottery/kz/5x36/results?limit=10
https://lucky-numbers.ru/api/v1/lottery/kz/6x49/results?limit=10
```

Официальный SZ.KZ используется как резервный источник через Playwright. Cloudflare может блокировать IP GitHub Runner, поэтому JSON endpoint является основным.

## Проверка и диагностика

1. На cron-job.org проверить `History`: запрос должен получить 204.
2. Открыть https://github.com/anadyrov/sz-loto-notifier/actions и найти запуск соответствующего времени.
3. Успешный workflow должен быть зелёным. В шаге `Poll SZ.KZ and notify Telegram` видны номер тиража или сообщения об ожидании.
4. При 401 проверить имя заголовка `Authorization` и значение `Bearer <token>`.
5. При 404 проверить URL, доступ PAT к репозиторию и `Contents: Read and write`.
6. Если 204 есть, но workflow отсутствует, проверить точное тело `loto536`/`loto649`.
7. Если workflow зелёный, но Telegram пуст, проверить GitHub Secrets и чат с ботом.

Инцидент 14–15 сентября 2026 года: в GitHub Actions находилась устаревшая Telegram-конфигурация. `getMe` проходил, но `sendMessage` возвращал HTTP 403. Secrets были синхронизированы с рабочим локальным `.env`; облачный `telegramtest` и обе восстановительные отправки после этого завершились успешно. Старый probe был усилен проверкой `getChat`.

## Безопасность

Никогда не помещать PAT GitHub, Telegram token или `.env` в документацию, Git, чат либо скриншоты. Засвеченный токен немедленно отозвать и заменить. Срок действия PAT нужно контролировать. Текущая HTTP-информация cron показывала окончание токена 13 декабря 2026 года — до этой даты создать новый и заменить его в обеих cron-задачах.

## Команды разработчика

```powershell
cd C:\Users\anadyrov\.codex\sz_tools
.\.venv\Scripts\python.exe -m py_compile main.py
.\.venv\Scripts\python.exe main.py --probe
git status --short
```

`--probe` не отправляет сообщение: он вызывает Telegram `getMe` и проверяет последние данные обеих игр.
