# TIMELINE — Goal Roadmap Builder

Визуальный конструктор дорожной карты (roadmap): цели, этапы, связи и сроки
на канвасе. Single-page приложение, бэкенд — FastAPI + SQLAlchemy.

## Стек

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic
- **DB:** PostgreSQL 16 (в prod / docker-compose), SQLite для локальной разработки
- **Deploy:** Docker + docker-compose, gunicorn (UvicornWorker)
- **Quality:** ruff, pytest, GitHub Actions CI

## Быстрый старт (Docker + PostgreSQL)

```sh
cp .env.example .env        # задайте POSTGRES_PASSWORD, TIMELINE_ADMIN_PASSWORD, TIMELINE_OBSERVER_PASSWORD
docker compose up --build
```

Приложение отдаётся напрямую на `http://<хост>:<APP_PORT>` (по умолчанию
`http://localhost:8000`). Postgres поднимается сервисом `db`, миграции
применяются при старте контейнера `app` (`alembic upgrade head`, затем `seed()`).
Для TLS/домена поставьте перед приложением собственный обратный прокси
(Caddy/nginx) и, если нужно, укажите `FORWARDED_ALLOW_IPS` (см. ниже).

## Локальная разработка (SQLite)

```sh
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python app\main.py          # http://127.0.0.1:8000 (reload в dev)
```

По умолчанию используется файл `roadmaps.db` в корне проекта. При первом старте
приложение само применяет миграции (`alembic upgrade head`), создаёт начальный
roadmap и пользователей (пароли берутся из env).

## Конфигурация

Все переменные — в `.env.example`. Ключевые:

| Переменная | Описание |
|---|---|
| `DATABASE_URL` | DSN базы (`postgresql+psycopg://...` или `sqlite:///...`) |
| `FORWARDED_ALLOW_IPS` | Доверенные прокси для `X-Forwarded-For` (по умолчанию `127.0.0.1`; `*` только за доверенным прокси) |
| `TIMELINE_ADMIN_USER` / `TIMELINE_ADMIN_PASSWORD` | Администратор (полный доступ) |
| `TIMELINE_OBSERVER_USER` / `TIMELINE_OBSERVER_PASSWORD` | Наблюдатель (только просмотр) |
| `TIMELINE_LOGIN_MAX_ATTEMPTS` / `TIMELINE_LOGIN_LOCKOUT_SECONDS` | Rate-limit входа |
| `TIMELINE_MAX_PAYLOAD_BYTES` | Лимит тела запроса |

В prod-окружении пароли обязательны (иначе `RuntimeError`); в dev при отсутствии
env-переменной генерируется разовый пароль и выводится в лог.

Смена пароля = изменение `TIMELINE_ADMIN_PASSWORD` / `TIMELINE_OBSERVER_PASSWORD`
в `.env` и рестарт контейнера: `seed()` синхронизирует пароли и роли с
конфигурацией (не трогает их, только если значение совпадает) и инвалидирует
все активные сессии пользователя. Legacy-хэши (старый формат/итерации)
автоматически перехешируются на PBKDF2-SHA256 600k.

## Prod-заметки

- **Запуск:** в prod `seed()` выполняется один раз в `docker-entrypoint.sh`
  (после `alembic upgrade head`) — до старта воркеров gunicorn, без гонок.
- **Ресайз воркеров:** gunicorn перезапускает воркер через каждые
  `GUNICORN_MAX_REQUESTS` (по умолчанию 1000, `GUNICORN_MAX_REQUESTS_JITTER`
  рандомизирует момент) — защита от утечек памяти.
- **Прокси и rate-limit:** по умолчанию `FORWARDED_ALLOW_IPS=127.0.0.1` —
  заголовок `X-Forwarded-For` игнорируется, лимит входа считает реальные IP.
  Если за приложением стоит доверенный прокси, укажите его IP (или `*`),
  иначе клиенты смогут подменять IP и обходить лимит.
- **Лимит тела:** приложение отвергает запросы > `TIMELINE_MAX_PAYLOAD_BYTES`
  (в т.ч. без `Content-Length`).
- **Статика:** `/static` отдаётся с `Cache-Control: immutable` и версионируется
  в `index.html` (`?v=`); при изменении статики поднимите номер версии.
- **Бэкапы:** боевые данные — в volume `pgdata`. Регулярно снимайте дампы:
  `./backup.sh` (складывает gzip-дампы в `backups/`, хранит последние
  `BACKUP_RETENTION` дней). Для автоматизации добавьте в cron, например:
  `0 3 * * * /opt/projects/timeline/backup.sh /opt/projects/timeline`.
- **Логи:** `app` пишет запросы и ошибки в stdout; docker-compose ограничивает
  размер логов (`json-file`, 10 МБ × 3 файла). Для централизованного сбора —
  настройте оркестрацию.
- **Обновление:** `docker compose up --build --pull` — миграции применятся
  автоматически при старте `app`.
- **Шрифты:** Satoshi/General Sans подгружаются с внешнего CDN Fontshare
  (единственный сторонний запрос). Для закрытых сетей — скачайте шрифты
  локально и обновите `index.html`/CSP (`style-src`/`font-src`).

## Миграции

```sh
alembic upgrade head        # применить
alembic revision --autogenerate -m "description"   # новая миграция
```

В prod миграции выполняются автоматически в `docker-entrypoint.sh`; при локальной
разработке их применяет `seed()` при старте приложения. Схема управляется **только**
через Alembic (без `create_all`).

## Зависимости

Версии зафиксированы через `pip-tools` (детерминированные сборки):

```sh
pip install pip-tools
pip-compile requirements.in          # обновить requirements.txt
pip-compile requirements-dev.in      # обновить requirements-dev.txt
```

## Тесты и линт

```sh
ruff check .
pytest tests -q             # CI гоняет тесты против PostgreSQL-сервиса
```

## Структура

```
app/
  main.py        # FastAPI, lifespan, middleware, /api/health
  config.py      # конфигурация из env
  db.py          # engine, seed(), _sync_users
  models.py      # Roadmap, User, LoginSession, LoginAttempt
  payload.py     # default_payload, миграция schema v1 → v2
  security.py    # PBKDF2-хэши, токены
  auth.py        # сессии и роли
  limiter.py     # rate-limit входа на БД
  routers/       # /api/auth, /api/roadmaps
alembic/         # миграции
templates/       # frontend (canvas)
static/          # статика
tests/           # pytest
backup.sh        # pg_dump-бэкап (docker compose exec)
```

## API

| Метод | Путь | Доступ | Описание |
|---|---|---|---|
| POST | `/api/auth/login` | публичный | Вход, возвращает bearer-токен |
| POST | `/api/auth/logout` | авторизованный | Завершение сессии |
| GET | `/api/auth/me` | авторизованный | Текущий пользователь и роль |
| GET | `/api/roadmaps` | авторизованный | Список roadmap (сводки) |
| GET | `/api/roadmaps/{id}` | авторизованный | Детали roadmap |
| POST | `/api/roadmaps` | admin | Создать roadmap |
| PUT | `/api/roadmaps/{id}` | admin | Обновить; `base_version` на верхнем уровне тела → конфликт 409 при устаревшей версии |
| DELETE | `/api/roadmaps/{id}` | admin | Удалить |
| GET | `/api/health` | публичный | Health-check (БД) |

## Лицензия

MIT — см. [LICENSE](LICENSE).
