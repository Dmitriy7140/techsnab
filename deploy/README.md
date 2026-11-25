# Развёртывание Techsnab

Compose запускает приложение из `master` на `th37.ru` и приложение из `staging` на `staging.th37.ru`. У каждого свой том SQLite и свой ключ Django. Caddy принимает соединения на портах 80 и 443 и автоматически продлевает сертификаты. Состояние сертификатов хранится в томе `caddy_data`.

На VPS файлы активных версий доступны в `/opt/techsnab/master` и `/opt/techsnab/staging`. Файл `/opt/techsnab/.env` содержит `MASTER_SOURCE` с абсолютным путём к исходникам основной версии, метки образов `PRODUCTION_REVISION` и `STAGING_REVISION`, а также два отдельных случайных значения `PRODUCTION_SECRET_KEY` и `STAGING_SECRET_KEY`.

Сборка и проверка выполняются из каталога активной версии `staging`.

```sh
sudo docker compose --env-file /opt/techsnab/.env up --build -d
sudo docker compose --env-file /opt/techsnab/.env ps
```

После замены исходников и метки образа стейдж можно обновить отдельно.

```sh
sudo docker compose --env-file /opt/techsnab/.env up --build -d --no-deps staging
```

Принятые заявки приложение записывает в журнал своего сервиса (`production` или `staging`).
