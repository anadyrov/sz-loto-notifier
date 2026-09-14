# SZ Loto Notifier

Облачный сервис результатов Loto 5/36 и Loto 6/49 с отправкой в Telegram.

Две задачи cron-job.org вызывают GitHub Actions в 21:05 и 22:05 по `Asia/Almaty`. После запуска сервис проверяет результат каждую минуту до появления, максимум три часа. Компьютер пользователя не требуется.

Полная актуальная настройка, диагностика и handoff: [OPERATIONS.md](OPERATIONS.md) и [HANDOFF.md](HANDOFF.md).

Секреты хранятся только в GitHub Actions Secrets и в настройках cron-job.org. Не добавляйте токены в репозиторий.
