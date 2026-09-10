# Уведомления о результатах SZ.KZ

Сервис отслеживает результаты Loto 5/36 и Loto 6/49 на SZ.KZ и отправляет новые результаты в Telegram. Подробная инструкция находится в [OPERATIONS.md](OPERATIONS.md).

## Запуск

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

1. В Telegram открыть `@BotFather`, выполнить `/newbot` и записать токен.
2. Написать созданному боту любое сообщение.
3. Получить `chat_id` через `https://api.telegram.org/bot<TOKEN>/getUpdates`.
4. Заполнить `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` в `.env`.
5. При необходимости указать числа билета в `TICKET_NUMBERS`, например `5,19,27,23,32`.

Запуск:

```powershell
.\.venv\Scripts\python.exe main.py
```

Для GitHub Actions используется команда `python main.py --once`. В репозитории
нужно добавить Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, а для SMS также
`SMS_ENABLED`, `SMS_PHONE` и `MOBIZON_API_KEY`.

Сервис должен работать постоянно на компьютере или VPS. В GitHub Actions он запускается раз в 5 минут в вечернем окне и сохраняет состояние между запусками.