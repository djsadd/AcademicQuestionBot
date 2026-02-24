# 🧠 Мультиагентный бот по академическим вопросам

Документ описывает **полную архитектуру**, **набор сервисов**, **взаимодействие агентов** и **технологический стек** для создания мультиагентного академического бота (университет / школа / EdTech).

---

## 1. Цели системы

* Единая точка входа для академических вопросов
* Разделение ответственности между агентами
* Минимизация ошибок и галлюцинаций
* Масштабируемость под разные вузы и правила
* Поддержка RAG (ответы на основе документов)

---

## 2. Общая архитектура (High-level)

```
[ Клиент (Telegram / Web) ]
            ↓
[ API Gateway / Backend (FastAPI) ]
            ↓
[ Agent Orchestrator ]
     ↓        ↓        ↓
[Agent A] [Agent B] [Agent C]
     ↓        ↓        ↓
   [ RAG / DB / Services ]
```

---

## 3. Основные сервисы

### 3.1 Client Layer

**Назначение:** пользовательский интерфейс

* Telegram Bot
* Web UI (React / Next.js)
* Mobile App (опционально)

📌 Отправляет **сырой запрос** пользователя

---

### 3.2 API Gateway / Backend

**Технологии:** FastAPI, REST / WebSocket

Функции:

* Авторизация
* Логирование
* Rate limiting
* Контекст пользователя (вуз, курс, язык)
* Передача запроса в Orchestrator

---

### 3.3 Agent Orchestrator (ключевой компонент)

**Назначение:** управление агентами

Функции:

* Классификация запроса
* Определение нужных агентов
* Последовательный / параллельный вызов
* Агрегация ответов
* Контроль качества

**Технологии:**

* LangGraph / CrewAI / AutoGen
* Custom routing logic

---

## 4. Агенты (Core Agents)

### 4.1 Intent Router Agent

**Роль:** понимает, *о чём вопрос*

Примеры intent:

* учеба
* GPA
* поступление
* документы
* дедлайны

Выход:

```json
{
  "intents": ["gpa", "study"],
  "priority": "high"
}
```

---

### 4.2 Academic Tutor Agent

**Роль:** учебная помощь

Функции:

* объяснение тем
* примеры
* подготовка к экзаменам

Источники:

* учебные материалы
* RAG

---

### 4.3 Academic Policy Agent

**Роль:** правила, регламенты, GPA

Функции:

* кредиты
* академическая честность
* отчисление / пересдачи

Источники:

* PDF регламентов
* приказы вуза

---

### 4.4 Admission Agent

**Роль:** поступление и гранты

Функции:

* требования
* дедлайны
* документы

---

### 4.5 Deadline & Schedule Agent

**Роль:** дедлайны и напоминания

Функции:

* календарь
* экзаменационные периоды
* интеграция с Google Calendar

---

### 4.6 Validator / Critic Agent

**Роль:** контроль качества

Функции:

* проверка логики
* выявление противоречий
* упрощение ответа

---

## 5. Взаимодействие агентов (Flow)

### Пример: «Как поднять GPA и не вылететь?»

1. Intent Router → GPA + Study
2. Policy Agent → правила GPA
3. Tutor Agent → стратегии обучения
4. Validator Agent → проверка
5. Orchestrator → единый ответ

---

## 6. RAG (Retrieval-Augmented Generation)

**Зачем:** ответы строго по правилам конкретного вуза

### Компоненты:

* Vector DB (Qdran)
* Embeddings (OpenAI)
* Document Loader (PDF, DOCX)

### Источники:

* регламенты
* учебные планы
* FAQ

### API для загрузки документов

* `POST /api/rag/documents/upload` — принимает файл (PDF/DOCX/TXT) и метаданные (JSON в поле `metadata`) и добавляет его в векторное хранилище.
* `GET /api/rag/documents/search?query=...&top_k=3` — возвращает найденные фрагменты контекста с их метаинформацией и score.
* `GET /api/rag/documents` — список всех загруженных документов (с `document_id`, размером, датой загрузки).
* `DELETE /api/rag/documents/{document_id}` — удаляет файл из стораджа и чистит связанные вектора в Qdrant.
* В docker-compose данных Qdrant сохраняются в volume `qdrant_data`, поэтому после перезапуска контейнера коллекции сохраняются.
* Параметры подключения к Qdrant (количество попыток и задержки) управляются переменными `QDRANT_RETRY_ATTEMPTS`, `QDRANT_RETRY_DELAY`, `QDRANT_RETRY_MAX_DELAY` в `.env`.
* Для локальной отладки можно включить in-memory fallback (`QDRANT_FALLBACK_ENABLED=true`), чтобы загрузка/поиск не падали, если Qdrant временно недоступен. По умолчанию переменная равна `false`, чтобы API не переходил в временный режим и не терял точки в Qdrant (в fallback данные не сохраняются между рестартами API).
* Если меняете модель эмбеддингов (и, соответственно, размер вектора), пересоздайте коллекцию Qdrant, чтобы размер совпадал.

---

## 7. Хранилища данных

### 7.1 Основная БД (PostgreSQL)

* пользователи
* вузы
* роли
* логи

### 7.2 Vector DB

* embeddings документов
* семантический поиск

### 7.3 Cache (Redis)

* частые вопросы
* контекст диалога

---

## 8. Технологический стек

### Backend

* Python 3.11
* FastAPI
* SQLAlchemy
* Celery / BackgroundTasks

### AI / Agents

* OpenAI API / Local LLM
* LangGraph / CrewAI
* RAG pipeline

### DevOps

* Docker
* Docker Compose
* Nginx
* CI/CD (GitHub Actions)

---

## 9. Безопасность и ограничения

* Role-based access (student / admin)
* Логи запросов
* Ограничения на академическое мошенничество
* Фильтрация опасных запросов

---

## 10. MVP (минимальный набор)

Для запуска MVP достаточно:

* Telegram Bot
* FastAPI
* Orchestrator
* 3 агента:

  * Intent Router
  * Academic Tutor
  * Policy Agent
* RAG с PDF регламентами

---

## 11. Возможности масштабирования

* Подключение новых вузов
* Мультиязычность
* Персональные рекомендации
* Аналитика запросов

---

## 12. Итог

Данная архитектура:

* модульная
* масштабируемая
* подходит для вузов и EdTech
* легко расширяется агентами

---

📌 Следующие шаги:

* диаграмма в Mermaid
* MVP-код (FastAPI + LangGraph)
* Telegram-бот
* адаптация под конкретный вуз

---

## 13. Структура проекта (Production-ready)

Ниже — рекомендуемая структура репозитория для **FastAPI + LangChain + мультиагентной архитектуры**.

```
academic-bot/
├── app/
│   ├── main.py                 # Точка входа FastAPI
│   ├── config/
│   │   ├── settings.py         # env, API keys, config
│   │   └── logging.py
│   │
│   ├── api/                    # HTTP / Webhook слой
│   │   ├── routers/
│   │   │   ├── chat.py          # /chat endpoint
│   │   │   ├── health.py
│   │   │   └── admin.py
│   │   └── deps.py             # зависимости (auth, db)
│   │
│   ├── agents/                 # ВСЕ АГЕНТЫ
│   │   ├── base.py             # BaseAgent (абстракция)
│   │   ├── intent_router.py    # Intent Router Agent
│   │   ├── tutor_agent.py      # Academic Tutor Agent
│   │   ├── policy_agent.py     # Academic Policy Agent
│   │   ├── admission_agent.py
│   │   ├── validator_agent.py
│   │
│   ├── orchestrator/
│   │   ├── graph.py            # LangGraph workflow
│   │   ├── router.py           # логика вызова агентов
│   │   └── aggregator.py       # сбор финального ответа
│   │
│   ├── langchain/
│   │   ├── llm.py              # инициализация LLM
│   │   ├── prompts/
│   │   │   ├── intent.txt
│   │   │   ├── tutor.txt
│   │   │   └── policy.txt
│   │   ├── tools/
│   │   │   ├── search.py
│   │   │   └── calculator.py
│   │   └── memory.py
│   │
│   ├── rag/
│   │   ├── loader.py           # PDF/DOCX загрузка
│   │   ├── embeddings.py
│   │   ├── retriever.py
│   │   └── vector_store.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   ├── models.py
│   │   └── crud.py
│   │
│   ├── services/
│   │   ├── user_context.py     # вуз, курс, язык
│   │   ├── permissions.py
│   │   └── analytics.py
│   │
│   └── workers/
│       └── tasks.py            # Celery / background
│
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── entrypoint.sh
│
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── README.md
└── scripts/
    └── ingest_docs.py          # загрузка документов в RAG
```

---

## 14. Роли ключевых файлов

### `agents/base.py`

Абстрактный класс агента:

* input schema
* run()
* tools

### `orchestrator/graph.py`

LangGraph:

* определяет порядок агентов
* параллельное / последовательное выполнение

### `api/routers/chat.py`

Единая точка общения:

* принимает вопрос
* передает в orchestrator
* возвращает ответ

---

## 15. Docker

### Dockerfile (API)

* Python 3.11
* FastAPI + LangChain
* Uvicorn

### Dockerfile.worker

* фоновые задачи
* ingestion документов

---

## 16. docker-compose.yml (минимум)

Сервисы:

* api
* postgres
* qdrant
* redis

---

## 17. Поток запроса (реально как в коде)

1. `/chat` → FastAPI
2. Context Service → вуз, язык
3. Intent Router Agent
4. Orchestrator → нужные агенты
5. RAG Retriever
6. Validator Agent
7. Ответ пользователю

---

## 18. Рекомендации

* Каждый агент = отдельный файл
* Prompts выносить в `.txt`
* RAG строго отделять от агентов
* Orchestrator не знает деталей агентов

---

## 19. Итоговая логика

FastAPI = инфраструктура
LangChain = интеллект
LangGraph = управление
Docker = продакшен

---

## 20. Docker Compose запуск

`docker-compose.yml` поднимает сервисы `api`, `frontend`, `celery`, `postgresql`, `qdrant` и `redis`.

Сборка и запуск:

```bash
docker compose up --build -d frontend api celery postgresql qdrant redis
```

Команда одновременно соберет образы и развернет нужные контейнеры.

### Персистентное хранилище документов

* В `.env` задаются `QDRANT_URL`, `QDRANT_COLLECTION`, `RAG_STORAGE_PATH`.
* Docker Compose использует volume `rag_storage`, чтобы API и Celery имели общий доступ к `/app/storage` (файлы для RAG).
* Для Qdrant добавлен volume `qdrant_data`, чтобы коллекции не терялись между перезапусками.
* Сервис `frontend` собирается через `docker/Dockerfile.frontend` (Vite → Nginx) и доступен на `http://localhost:18030`.

## 21. LLM (финальный ответ)

* Финальный ответ собирает LLM на основе выводов агентов и контекста RAG.
* Настройки задаются через `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDINGS_MODEL`, `OPENAI_EMBEDDINGS_DIM` (см. `.env.example`).
* В `backend/langchain/prompts/final_answer.txt` лежит промпт, который управляет стилем ответа и ссылками на источники.
* Если ключа нет, система вернёт конкатенацию частичных ответов.

## 22. Frontend (Vite + React)

Фронтенд находится в директории `frontend/` и предоставляет:

* hero-экран с кратким статусом сервиса;
* панель управления RAG-документами (список файлов, загрузка, удаление);
* подготовку к интеграции чат-виджета.

### Настройка и запуск

```bash
cd frontend
cp .env.example .env              # при необходимости поменяйте VITE_API_BASE_URL
npm install                       # установите зависимости
npm run dev                       # локальная разработка на http://localhost:5173
npm run build                     # production-сборка
npm run preview                   # предпросмотр собранной версии
```

Параметр `VITE_API_BASE_URL` должен указывать на backend (`http://localhost:18000/api`), чтобы загрузка/удаление документов работали без прокси.

### Docker

Фронтенд также собирается в контейнер через `docker/Dockerfile.frontend` и запускается как сервис `frontend`:

```bash
docker compose up --build frontend
```

По умолчанию он доступен на `http://localhost:18030` и проксирует запросы в backend по внутреннему адресу `http://api:8000/api`.
# AcademicQuestionBot
# AcademicQuestionBot
