# Развёртывание Techsnab

Compose запускает приложение из `master` на `th37.ru` и приложение из `staging` на `staging.th37.ru`. У каждого свой том SQLite и свой ключ Django. Caddy принимает соединения на портах 80 и 443 и автоматически продлевает сертификаты. Состояние сертификатов хранится в томе `caddy_data`.

На VPS файлы активных версий доступны в `/opt/techsnab/master` и `/opt/techsnab/staging`. Файл `/opt/techsnab/.env` содержит `MASTER_SOURCE` с абсолютным путём к исходникам основной версии, метки образов `PRODUCTION_REVISION` и `STAGING_REVISION`, а также два отдельных случайных значения `PRODUCTION_SECRET_KEY` и `STAGING_SECRET_KEY`.

Для входа на стейдж Caddy читает файл `/opt/techsnab/auth/staging-users`. В нём одна строка с логином и bcrypt-хешем, разделёнными пробелом. Хеш можно получить командой `caddy hash-password`. При замене файла по новому inode пересоздайте сервис `proxy`, чтобы обновить bind mount.

Сборка и проверка выполняются из каталога активной версии `staging`.

```sh
sudo docker compose --env-file /opt/techsnab/.env up --build -d
sudo docker compose --env-file /opt/techsnab/.env ps
```

После замены исходников и метки образа стейдж можно обновить отдельно.

```sh
sudo docker compose --env-file /opt/techsnab/.env up --build -d --no-deps staging
```

Заявки и статистика основного сайта хранятся в SQLite в постоянном томе `production_data`. Стейдж хранит свои заявки и аналитику в `staging_data`. График считает первое посещение браузера с согласием на аналитические cookie.

Кабинет доступен на `https://admin.th37.ru/`. Менеджеру нужны флаг Django `is_staff`, права `landing.view_lead`, `landing.change_lead`, `landing.view_trafficevent`, `reviews.view_review`, `reviews.add_review` и `reviews.change_review`.

На основном сайте и стейдже форма отзывов включена через `PUBLIC_REVIEWS=1`. Кабинет модерирует отзывы в общем томе `reviews_data`, миграции которого выполняет production. Резервируйте SQLite-базы всех трёх томов.
