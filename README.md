# Сортировка обращений поддержки

Сервис принимает текст обращения, вызывает модель и сохраняет результат в SQLite.

Маршрута `POST /lead` в проекте нет. Рабочий метод — `POST /triage`. Письма сервис не отправляет: `email` — это значение поля `channel`.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

На Linux и macOS: `source .venv/bin/activate` и `cp .env.example .env`.

В `.env` укажите `OPENAI_API_KEY`. Без ключа сервер стартует, но `/triage` отдаёт запасной ответ, а в таблице в `error` будет `empty_api_key`.

## Запуск

Из корня репозитория:

```bash
python -m app.db
uvicorn app.main:app --reload
```

`python -m app.db` создаёт `data/triage.db` и таблицу `tickets`. При старте API таблица создаётся сама, если её ещё нет.

Проверка: `http://127.0.0.1:8000/health` → `{"status":"ok"}`.

## Пример запроса к POST /triage

```bash
curl -sS -X POST http://127.0.0.1:8000/triage ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Не пришёл чек об оплате заказа 1042\",\"channel\":\"email\",\"client_id\":\"demo-1\"}"
```

На Linux и macOS вместо `^` используйте `\`.

Тело запроса:

- `text` — строка 1–2000 символов
- `channel` — `email`, `form` или `chat`
- `client_id` — строка 1–64 символов

Успех: `200` и JSON с `category`, `draft_reply`, `confidence`, `escalate`.

Неверный JSON даёт `422` — строка в базу не пишется. Больше пяти запросов с одним `client_id` за минуту дают `429`.

Форма в браузере: `http://127.0.0.1:8000/docs`.

## Где смотреть SQLite

Файл: `data/triage.db`. Таблица: `tickets`.

Колонки: `id`, `created_at`, `client_id`, `channel`, `text`, `category`, `confidence`, `escalate`, `draft_reply`, `error`.

В DBeaver: New Database Connection → SQLite → путь к `data/triage.db` → таблица `tickets` → View Data. Файл `.db` в Cursor как текст не открывайте.

Если таблица кажется пустой: Disconnect и Connect заново.

## Где смотреть журнал

JSON-событие пишется в терминал, где запущен `uvicorn`. В нём есть `client_id`, `channel`, `category`, `confidence`, `escalate`, `был_ли_error`. Текста обращения и ключа API там нет.

Отдельной папки `log/` и отправки почты нет. Канал `email` видно в запросе, в SQLite (`tickets.channel`) и в этом JSON.
