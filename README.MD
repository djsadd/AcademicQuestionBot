# Academiq — академический ИИ-ассистент TAU

Мультиагентный ассистент Turan-Astana University: отвечает абитуриентам (публичный чат приёмной комиссии) и студентам (персональный чат с данными Platonus) по официальным данным университета — регламентам, документам, календарю и приёмной информации.

- **Backend:** FastAPI · мультиагентный пайплайн · RAG (Qdrant) · PostgreSQL · Celery/Redis
- **Frontend:** React 18 + Vite, светлая/тёмная тема, адаптивный дизайн
- **Каналы:** веб-чат (SSE-стриминг), Telegram-бот, Telegram Mini App

---

## Пайплайн ИИ-агентов

```
                 ┌─────────────┐
 вопрос ───────► │ Intent      │  правила (0 мс) → LLM JSON, до 2 интентов
                 │ Router      │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │ Planner     │  интенты → набор агентов (graph.py)
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │ Retrieval   │  ОДИН поиск в Qdrant на запрос, общий для агентов,
                 │ (RAG)       │  фильтр по score, параллельное LLM-сжатие чанков
                 └──────┬──────┘
          ┌─────────────┼─────────────┐        агенты выполняются ПАРАЛЛЕЛЬНО,
          ▼             ▼             ▼        с таймаутом и изоляцией ошибок
     ┌─────────┐   ┌─────────┐   ┌──────────┐  ┌──────────┐
     │ Policy  │   │ Tutor   │   │Admission │  │ Dean     │
     │регламенты│  │учёба    │   │приёмная  │  │календарь,│
     └────┬────┘   └────┬────┘   └────┬─────┘  │ доступ   │
          └─────────────┼─────────────┘        └────┬─────┘
                        ▼                           │
                 ┌─────────────┐  ◄─────────────────┘
                 │ Synthesizer │  стриминг LLM-ответа токенами (или готовый
                 │             │  ответ агента без LLM — direct_response)
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐  HTML allow-list, проверка цифр по источникам
                 │ Validator   │  (цены, баллы, даты), пометка непроверенных данных
                 └──────┬──────┘
                        ▼
                SSE: stage → delta → done
```

| Интент | Агенты |
|---|---|
| `admission` | Admission (структурированные данные приёмной + диалог со слотами) |
| `gpa` | Policy + Tutor |
| `study` | Tutor |
| `documents`, `general` | Policy |
| `calendar`, `deadline`, `password_reset` | Dean |

Каждое событие пайплайна (`stage`) стримится во фронтенд — пользователь видит, что делает ассистент («Ищу в документах…», «Проверяю факты…»), а в аналитике сохраняется трасса с длительностью каждого шага (`timings_ms`).

Ключевые файлы: [orchestrator/pipeline.py](backend/orchestrator/pipeline.py), [orchestrator/graph.py](backend/orchestrator/graph.py), [agents/](backend/agents/), [langchain/prompts/final_answer.txt](backend/langchain/prompts/final_answer.txt).

---

## Быстрый старт (Docker)

```bash
cp .env.example .env          # заполните OPENAI_API_KEY, JWT_SECRET, TELEGRAM_BOT_TOKEN, PLATONUS_*
docker compose up --build -d
```

| Сервис | Адрес |
|---|---|
| Веб-приложение | http://localhost:18030 |
| API (только через nginx фронтенда по умолчанию) | http://127.0.0.1:18000/api |
| Swagger (не в production) | http://127.0.0.1:18000/api/docs |

Проверки состояния: `GET /api/health` (liveness) и `GET /api/health/ready` (БД + Qdrant).

### ⚠️ Миграция существующего деплоя

Раньше у PostgreSQL **не было именованного volume** — данные жили в анонимном томе контейнера. Теперь используется `academicquestionbot_postgres_data`. Перед первым `docker compose up` на сервере с данными перенесите их:

```bash
docker compose exec postgresql pg_dump -U bot bot > backup.sql   # на СТАРОЙ версии compose-файла
# обновите код, затем:
docker compose up -d postgresql
docker compose exec -T postgresql psql -U bot bot < backup.sql
```

Также порты Postgres/Redis/Qdrant/API теперь опубликованы только на `127.0.0.1`. Если API нужен снаружи напрямую — задайте `API_BIND=0.0.0.0`.

---

## Локальная разработка

```bash
# Backend (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d postgresql redis qdrant
uvicorn backend.api.main:app --reload --port 18000

# Frontend
cd frontend && npm install
VITE_API_BASE_URL=http://localhost:18000/api npm run dev
```

Тесты и линтер:

```bash
pytest -q backend/tests          # без сети и без платных API (см. backend/tests/conftest.py)
ruff check backend --select F,E9
cd frontend && npm run build     # tsc + vite
```

CI (GitHub Actions) запускает то же самое: [.github/workflows/ci.yml](.github/workflows/ci.yml).

---

## Конфигурация

Все переменные описаны в [.env.example](.env.example) и читаются через [backend/core/config.py](backend/core/config.py). Важное для production:

| Переменная | Назначение |
|---|---|
| `APP_ENV=production` | отключает Swagger, падает при недоступной БД на старте |
| `CORS_ORIGINS` | список доменов фронтенда (не `*`) |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` | любой OpenAI-совместимый сервер (OpenAI, vLLM, Ollama…) |
| `OPENAI_FAST_MODEL` | дешёвая модель для роутинга и сжатия контекста |
| `PUBLIC_RATE_LIMIT_PER_MINUTE` | защита бюджета LLM на публичном чате (на процесс API) |
| `RAG_TOP_K`, `RAG_MIN_SCORE` | сколько чанков брать и порог релевантности |
| `AGENT_TIMEOUT_SECONDS` | таймаут одного агента |
| `DB_POOL_MAX` | размер пула соединений Postgres на процесс |
| `LOG_JSON=true` | структурированные логи с `request_id` |
| `ADMIN_LOGINS` | логины Platonus, которые всегда администраторы (назначить первого админа) |
| `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP` | размер фрагмента и перекрытие при нарезке документов |

> При смене модели эмбеддингов (размерности вектора) пересоздайте коллекцию Qdrant — иначе поиск вернёт ошибку размерности (теперь она обрабатывается мгновенно, без зависания запроса).

---

## База знаний (RAG)

Раздел **«База знаний»** в кабинете администратора (`/rag`):

- загрузка нескольких файлов (drag & drop) с названием, категорией и аудиторией; дубликаты определяются по SHA-256;
- нарезка по структуре документа: страницы PDF, заголовки и таблицы DOCX, границы абзацев и предложений; у каждого фрагмента есть страница и раздел, которые показываются в источниках ответа;
- гибридный поиск: смысловой (векторы) + по ключевым словам с учётом словоформ;
- вкладка «Проверка поиска» показывает ровно те фрагменты, которые получат агенты;
- переиндексация документа или всей базы, пересоздание индекса при смене модели эмбеддингов (интерфейс сам предупреждает о несовместимости);
- если Celery недоступен, индексация выполняется в процессе API, так что загрузка не зависает.

Массовая загрузка из папки:

```bash
python -m scripts.ingest_docs "Документы/Внутренние нормативные документы" --category regulation --audience students
```

## Структура

```
backend/
  core/            настройки, логирование, rate limiting
  api/             FastAPI: main.py (middleware, health), routers/
  orchestrator/    pipeline.py, graph.py, aggregator.py, router.py
  agents/          intent, policy, tutor, admission(+dialogue), dean, validator
  rag/             loader, embeddings (батчи + кэш), vector_store, compression
  langchain/       LLM-клиент, промпты, инструменты (admission_info, calendar…)
  db/              пул соединений + доступ к таблицам
  telegram_service/, workers/, platonus_api/
frontend/src/
  components/chat/     чат: ChatWorkspace, MessageItem, Composer, AgentProgress
  components/layout/   AppShell (кабинет), PublicHeader
  components/ui/       иконки, логотип, переключатель темы
  styles/              tokens.css (дизайн-токены), base, shell, chat, landing, admin
docker/            Dockerfile'ы и nginx
docs/              подробности пайплайна приёмной комиссии
```

Подробнее об admission-агенте: [docs/public_admission_agent_pipeline.md](docs/public_admission_agent_pipeline.md).
