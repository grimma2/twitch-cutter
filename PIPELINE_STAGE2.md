# Stage 2 Pipeline (VOD -> Opus -> Clips -> YouTube)

Этот пайплайн реализован в `main.py`.

## Что делает

1. Принимает webhook `end_download` от LiveStreamDVR.
2. Публикует VOD как публичный URL: `local_http` (локальный nginx) или `dropbox` (загрузка в Dropbox).
3. Создает проект в Opus (`/api/clip-projects`).
4. Ждет появление клипов (`/api/exportable-clips`), максимум 5 минут.
5. Скачивает клипы.
6. Загружает клипы на YouTube через OAuth.

## Подготовка

1. Установите зависимости:

```bash
pip install -r requirements.txt
```

2. Создайте `.env` из шаблона:

```bash
cp .env.example .env
```

3. Заполните минимум:
- `OPUS_BEARER_TOKEN`
- `YT_CLIENT_SECRET_FILE`
- `TRIGGER_MODE=webhook`
- Для `PUBLISH_MODE=local_http`: `PUBLIC_BASE_URL`, `PUBLIC_OUTPUT_DIR`
- Для `PUBLISH_MODE=dropbox`: `DROPBOX_ACCESS_TOKEN`, `DROPBOX_FOLDER` (по умолчанию `/twitch_vods`)

## Nginx для выдачи файлов и webhook

Добавьте два location-блока в ваш `server` для `twitchcheker.online`:

```nginx
location /public_vods/ {
    alias /var/www/twitchcheker/public_vods/;
    autoindex off;
}

location /webhook/livestreamdvr {
    proxy_pass http://127.0.0.1:8090/webhook/livestreamdvr;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

И параметры в `.env`:
- `WEBHOOK_PORT=8090`
- Для `local_http`: `PUBLIC_OUTPUT_DIR=/var/www/twitchcheker/public_vods`, `PUBLIC_BASE_URL=https://twitchcheker.online/public_vods`
- Для `dropbox`: Opus принимает видео с Dropbox. Создайте приложение на https://www.dropbox.com/developers/apps, получите Access Token (scope: `files.content.write`, `sharing.write`), укажите `DROPBOX_ACCESS_TOKEN` и `DROPBOX_FOLDER`.

## Запуск

Одноразовый запуск (по умолчанию):

```bash
python main.py
```

Непрерывный режим (слушать webhook всегда):

```bash
RUN_ONCE=false python main.py
```

Обработка конкретного файла:

```bash
VOD_FILE=./data/storage/vods/channel/some_vod.ts python main.py
```

## Настройка LiveStreamDVR webhook

В LiveStreamDVR (Settings -> Config):
- `Webhook URL` = `https://twitchcheker.online/webhook/livestreamdvr`

## Примечания

- Текущий bearer-токен Opus в ваших markdown похож на реальный секрет. Лучше перевыпустить.
- Первый запуск YouTube OAuth откроет браузер для авторизации и сохранит `youtube_token.json`.
- Повторная обработка одного и того же VOD блокируется через `processed_vods.json`.
