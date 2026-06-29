- `backend` - FastAPI API, SQLAlchemy, Alembic, MySQL, интеграция с T-Invest API, ML-прогнозы и фоновые задачи.
- `PROJECT-MONEY/registration-form` - React-приложение с авторизацией, портфелем, рынком, аналитикой, моделями и backtest-разделом.
- `docker-compose.yml` - полный локальный стенд: MySQL + backend + frontend.

## Что нужно для запуска

Обязательно:

- Docker Desktop с Docker Compose v2.
- Свободные порты:
  - `3000` - frontend;
  - `8000` - backend API;
  - `3306` - MySQL.
- Доступ в интернет при первой сборке образов: Docker скачивает базовые образы, backend устанавливает Python-зависимости, frontend устанавливает npm-пакеты.
- Для полноценной работы торговых и рыночных функций нужен T-Invest API token. Без него интерфейс и backend могут запуститься, но операции с брокером, инструментами, свечами, счетами и заявками будут возвращать ошибку.

Для локального запуска без Docker дополнительно нужны:

- Python `3.11`.
- Node.js `20` и npm.
- MySQL `8.0`.
- Доступ к Python package index из `backend/requirements.txt`, включая `https://opensource.tbank.ru/...`, потому что проект использует `t-tech-investments==1.49.0`.

## Быстрый запуск через Docker

Из корня проекта выполните:

```powershell
docker compose up --build
```

После успешного запуска:

- frontend: `http://127.0.0.1:3000`
- backend healthcheck: `http://127.0.0.1:8000/health`
- backend root: `http://127.0.0.1:8000/`

Что делает `docker-compose.yml`:

- поднимает MySQL 8.0 с базой `trading`, пользователем `user` и паролем `password`;
- собирает backend из `backend/Dockerfile`;
- перед стартом backend выполняет `alembic upgrade head`;
- запускает API командой `uvicorn app.main:app --host 0.0.0.0 --port 8000`;
- собирает React-приложение и запускает его через nginx на порту `3000`;
- проксирует запросы frontend по `/api/` на backend.

Полезные команды:

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
docker compose down
```

Если нужно полностью сбросить локальную базу вместе с данными:

```powershell
docker compose down -v
```

Команда удалит volume `db_data`, поэтому пользователи, свечи, сделки, модели и история будут потеряны.

## Первый вход и T-Invest token

1. Откройте `http://127.0.0.1:3000`.
2. Зарегистрируйте пользователя.
3. Укажите T-Invest API token при регистрации или позже в настройках пользователя.
4. По умолчанию проект работает в sandbox-режиме: `USE_SANDBOX=true`.
5. Для sandbox-операций можно открыть sandbox-счет и пополнить его из интерфейса.

В docker-compose для backend глобальный `TINKOFF_API_KEY` оставлен пустым. Основной рабочий сценарий - хранить токен у конкретного пользователя через UI. Токен шифруется на backend с использованием `TOKEN_ENCRYPTION_KEY` или `SECRET_KEY`.

## Переменные окружения backend

Пример лежит в `backend/.env.example`. В Docker-режиме основные значения уже прописаны в корневом `docker-compose.yml`; при локальном запуске скопируйте пример в `.env`.

```powershell
cd backend
Copy-Item .env.example .env
```

Основные переменные:

- `APP_ENV` - окружение: `development`, `test`, `staging`, `production`.
- `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DB` - подключение к MySQL.
- `TINKOFF_API_KEY` - глобальный fallback-токен T-Invest. Обычно удобнее задавать токен у пользователя в интерфейсе.
- `USE_SANDBOX` - `true` для песочницы T-Invest, `false` для реального режима.
- `SECRET_KEY` - ключ подписи JWT/cookie. В production нельзя оставлять значение по умолчанию.
- `TOKEN_ENCRYPTION_KEY` - ключ шифрования T-Invest токенов пользователей. В production должен быть задан явно.
- `AUTH_COOKIE_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_HTTPONLY`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_MAX_AGE_SECONDS` - настройки auth-cookie.
- `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS` - ограничение частоты попыток входа.
- `AUTO_SELL_WORKER_ENABLED` - включает фоновую автопродажу.
- `AUTO_SELL_MANUAL_PROCESS_ENABLED` - разрешает ручной запуск обработки автопродаж через API.
- `AUTO_SELL_DRY_RUN` - режим без фактического выставления заявок.
- `AI_BOT_REAL_TRADING_ENABLED` - предохранитель для реальной торговли. Держите `false`, пока сознательно не включаете реальный режим.
- `BULK_TRADE_WORKER_ENABLED` - включает фоновый worker для массовых sandbox-сделок.
- `BULK_TRADE_WORKER_POLL_SECONDS` - интервал фоновой обработки.
- `BULK_TRADE_CSV_DIR` - папка для CSV-выгрузок массовых сделок.

Для production или staging backend проверяет безопасность настроек: нельзя использовать дефолтный `SECRET_KEY`, нельзя оставлять пустой `TOKEN_ENCRYPTION_KEY`, а `AUTH_COOKIE_SECURE` должен быть `true`.

## Переменные окружения frontend

Пример лежит в `PROJECT-MONEY/registration-form/.env.example`.

```powershell
cd PROJECT-MONEY\registration-form
Copy-Item .env.example .env
```

Основные переменные:

- `HOST=127.0.0.1` - адрес dev-сервера React.
- `PORT=3000` - порт frontend.
- `REACT_APP_API_BASE_URL=http://127.0.0.1:8000/` - адрес backend API при локальном запуске через `npm start`.
- `REACT_APP_DEBUG_API=false` - включает или отключает отладочные логи API-запросов в браузере.

В Docker-сборке frontend использует `REACT_APP_API_BASE_URL=/api/`, потому что nginx внутри frontend-контейнера проксирует `/api/` на backend.

## Локальный запуск без Docker

Этот режим удобен для разработки, когда backend и frontend запускаются отдельными процессами.

### 1. Запустить MySQL

Можно использовать только сервис базы из корневого compose-файла:

```powershell
docker compose up -d db
```

Параметры подключения должны совпадать с `backend/.env`:

```env
MYSQL_USER=user
MYSQL_PASSWORD=password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=trading
```

### 2. Подготовить backend

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверьте backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Ожидаемый здоровый ответ содержит `status: ok` и `database: ok`.

### 3. Подготовить frontend

В новом терминале:

```powershell
cd PROJECT-MONEY\registration-form
npm ci
Copy-Item .env.example .env
npm start
```

React dev server откроется на `http://127.0.0.1:3000`.

## Миграции базы данных

Схема БД управляется через Alembic.

В Docker-режиме миграции выполняются автоматически при старте backend-контейнера:

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

При локальном запуске миграции нужно применять вручную из папки `backend`:

```powershell
alembic upgrade head
```

Если база была создана старой версией проекта и MySQL ругается на `caching_sha2_password`, проще пересоздать локальный dev-volume:

```powershell
docker compose down -v
docker compose up --build
```

## Проверка штатной работы

После запуска проверьте:

1. `docker compose ps` показывает, что `db`, `backend` и `frontend` запущены.
2. `http://127.0.0.1:8000/health` возвращает `database: ok`.
3. `http://127.0.0.1:3000` открывает интерфейс.
4. Регистрация и вход проходят без ошибок.
5. В настройках пользователя задан валидный T-Invest token.
6. В sandbox-режиме доступны счета, пополнение sandbox-счета, рыночные данные и торговые операции.

Если frontend открывается, но API-запросы падают:

- при Docker-запуске проверьте логи `frontend` и `backend`;
- при локальном запуске проверьте `REACT_APP_API_BASE_URL` в frontend `.env`;
- проверьте, что backend действительно доступен на `http://127.0.0.1:8000`;
- после изменения frontend `.env` перезапустите `npm start`.

## Тесты и сборка

Backend:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
pytest
```

Frontend:

```powershell
cd PROJECT-MONEY\registration-form
npm ci
npm run test:ci
npm run build
npm run audit:prod
```
