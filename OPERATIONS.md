# Инструкция по сервису SZ.KZ

## Что делает сервис

Сервис проверяет результаты двух игр АО «Сәтті Жұлдыз» и отправляет уведомления:

- Loto 5/36: начало проверок в 21:00 по времени Алматы;
- Loto 6/49: начало проверок в 22:00 по времени Алматы;
- после начала проверки запрос повторяется каждую минуту локально;
- GitHub Actions запускает один job в 21:00 по Алматы, а job проверяет сайт каждую минуту около трех часов;
- один и тот же тираж не отправляется повторно;
- для 6/49 бонусный шар отправляется отдельной строкой.

## Каналы уведомлений

Telegram является основным каналом. SMS через Mobizon подключается только при `SMS_ENABLED=true`.
Если SMS отключены или Mobizon не принимает направление, Telegram продолжает работать.

Сервис также отправляет не чаще одного раза в день диагностические сообщения:

- сайт SZ.KZ недоступен;
- результат еще не опубликован.

После появления результата отправляется обычное уведомление с номером тиража и числами.

## Файлы

- `main.py` - основная логика проверки и отправки;
- `requirements.txt` - Python-зависимости;
- `.env.example` - пример локальной конфигурации;
- `.github/workflows/loto.yml` - расписание GitHub Actions;
- `last_draw_536.txt`, `last_draw_649.txt` - состояние последних отправленных тиражей;
- `status_536.json`, `status_649.json` - состояние диагностических уведомлений.

Файлы `.env`, `.venv`, состояния и API-ключи не должны попадать в Git.

## Локальный запуск

Из каталога проекта:

```powershell
cd C:\Users\anadyrov\.codex\sz_tools
.\.venv\Scripts\python.exe main.py
```

Одноразовая проверка последних опубликованных результатов:

```powershell
.\.venv\Scripts\python.exe main.py --latest
```

Одна плановая проверка без бесконечного цикла:

```powershell
.\.venv\Scripts\python.exe main.py --once
```

## GitHub Actions

Репозиторий: https://github.com/anadyrov/sz-loto-notifier

Workflow: `Loto results notifier`.

В GitHub откройте `Settings -> Secrets and variables -> Actions` и добавьте Secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
SMS_ENABLED
SMS_PHONE
MOBIZON_API_KEY
```

Значения секретов не записываются в репозиторий. Для временного отключения SMS установите:

```text
SMS_ENABLED=false
```

Для ручного запуска: `Actions -> Loto results notifier -> Run workflow`.

Расписание cron указано в UTC: `16:00 UTC` соответствует `21:00` в Алматы.
GitHub Actions может запустить cron с задержкой, но один длительный job надежнее серии коротких cron-запусков.

## SMS Mobizon

API Mobizon использует endpoint `https://api.mobizon.kz/service/message/sendsmsmessage`.
Номер передается в формате `770XXXXXXXX`, без плюса, пробелов и дефисов.

Если API отвечает, что для направления нет возможности отправки SMS, это ограничение тарифа или оператора,
а не ошибка Telegram. Нужно обратиться в поддержку Mobizon и попросить разрешить сервисные SMS на направление.

Секреты Mobizon нельзя публиковать в чатах, коммитах или скриншотах. При утечке API-ключ следует обновить в панели Mobizon.

## Безопасность и восстановление

1. Не добавляйте `.env` в Git.
2. Не вставляйте Telegram-токен и Mobizon API-ключ в Issues, README или сообщения.
3. При утечке Telegram-токена выполните `/revoke` в `@BotFather`, создайте новый и обновите GitHub Secret.
4. При утечке Mobizon-ключа нажмите обновление ключа в панели API и замените GitHub Secret.
5. Если облачный workflow перестал работать, сначала откройте последний запуск в `Actions` и проверьте шаг `Check lottery results once`.

## Изменение проекта

После изменений:

```powershell
git add .
git commit -m "Describe the change"
git push origin main
```

После push GitHub Actions использует новую версию автоматически. Для локального теста сначала запускайте `--once`.