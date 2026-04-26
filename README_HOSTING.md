# Deploy бота на хостинг

Этот проект подготовлен для запуска как `worker` (long polling) и не требует веб-сервера.

## 1. Что уже настроено в проекте

- `bot.py` — точка входа.
- `requirements.txt` — зафиксированные версии зависимостей (предсказуемая сборка).
- `Procfile` — команда запуска worker-процесса.
- `Dockerfile` — сборка и запуск в контейнере.
- `.env.example` — шаблон переменных окружения.

## 2. Обязательные переменные окружения

- `BOT_TOKEN` — токен бота от BotFather.
- `ADMIN_IDS` — ID админов через запятую, пример: `123456789,987654321`.

Рекомендуемые:

- `DB_PATH` — путь к SQLite базе.
- `RATE_LIMIT_SECONDS=0.7`
- `PAYMENT_MODE=simulate` или `crypto_pay`
- `CRYPTO_PAY_API_TOKEN` (если используете `crypto_pay`)
- `CRYPTO_PAY_BASE_URL=https://pay.crypt.bot/api`
- `WELCOME_STICKER_ID=`
- `SCHEDULER_TICK_SECONDS=15`

## 3. Важно про SQLite на хостинге

Если диск эфемерный, база пропадёт после рестарта контейнера.
Поэтому на хостинге обязательно:

1. Подключить persistent disk / volume.
2. Указать `DB_PATH` внутри этого диска, например:
   - Render: `DB_PATH=/var/data/bot.sqlite3`
   - Railway volume: `DB_PATH=/data/bot.sqlite3`
   - VPS: `DB_PATH=/opt/service-bot/data/bot.sqlite3`

## 4. Deploy на Render (рекомендуется)

1. Создайте `Background Worker`.
2. Подключите репозиторий.
3. Build Command:
   - `pip install -r requirements.txt`
4. Start Command:
   - `python -u bot.py`
5. Добавьте переменные окружения из блока выше.
6. Подключите persistent disk и задайте `DB_PATH` на этот диск.

## 5. Deploy на Railway

1. `New Project` -> `Deploy from GitHub`.
2. Добавьте переменные окружения.
3. Start Command:
   - `python -u bot.py`
4. Подключите volume и укажите `DB_PATH` внутри volume.

## 6. Deploy через Docker

Сборка:

```bash
docker build -t service-bot .
```

Запуск:

```bash
docker run -d --name service-bot --restart always --env-file .env -v bot_data:/data service-bot
```

Для Docker-тома задайте в `.env`:

```env
DB_PATH=/data/bot.sqlite3
```

## 7. Deploy на VPS (systemd)

Пример unit-файла:

```ini
[Unit]
Description=Telegram Service Bot
After=network.target

[Service]
WorkingDirectory=/opt/service-bot
ExecStart=/opt/service-bot/.venv/bin/python -u /opt/service-bot/bot.py
Restart=always
RestartSec=3
EnvironmentFile=/opt/service-bot/.env

[Install]
WantedBy=multi-user.target
```

Команды:

```bash
sudo systemctl daemon-reload
sudo systemctl enable service-bot
sudo systemctl restart service-bot
sudo systemctl status service-bot
```

## 8. Проверка перед продом

1. Бот отвечает на `/start`.
2. Админ видит кнопку админки (проверен `ADMIN_IDS`).
3. Создание заявки работает.
4. Если `PAYMENT_MODE=crypto_pay`, проверена генерация invoice.
5. Логи без ошибок при старте.
6. После рестарта хостинга данные в базе сохранились.
