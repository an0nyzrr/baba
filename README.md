# SpidTok server

Команда: spidos team · кодер: Найзер

Что делает:
- `GET /badges.json` — бейджи для мода (из базы, не из файла)
- `GET /version.json` — последняя версия
- `GET /links.json` — канал и контакт для покупки
- бот: `/donate` (заявка от юзера), одобрить/отклонить кнопками у админа
  (одобрение выдаёт галочку автоматически), `/grant ник бейдж`, `/revoke ник бейдж`,
  `/badges ник`, `/pending`

Ник TikTok → числовой id → всё дальше ключуется по id (ник может сменить хозяина, id — нет).

## Запуск

```
cp .env.example .env   # заполнить BOT_TOKEN и ADMIN_IDS
pip install -r requirements.txt
python main.py
```

## Деплой (systemd)

```
sudo useradd -r -m spidtok
sudo mkdir -p /var/lib/spidtok && sudo chown spidtok /var/lib/spidtok
sudo cp -r . /opt/spidtok && sudo chown -R spidtok /opt/spidtok
sudo cp deploy/spidtok.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now spidtok
```

Перед nginx поставить rate limit на `/donate`-подобный трафик — бот сам по себе
лимитов не держит, кроме `GRANT_COOLDOWN`.
