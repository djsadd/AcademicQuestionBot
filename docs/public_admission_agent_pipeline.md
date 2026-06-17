# Пайплайн ИИ-агента публичного чата приемной комиссии

Документ описывает текущую реализацию публичного admission-чата: HTTP endpoints, выбор структурированного admission-инструмента, сбор контекста для LLM и место, где в контекст попадают проходные/пороговые баллы.

## Короткий ответ по пороговым баллам

Получение пороговых баллов находится здесь:

- `backend/langchain/tools/admission_info.py`
  - `classify_admission_tool()` определяет, что вопрос относится к `passing_scores`;
  - `get_passing_scores()` читает `backend/data/admission_info.json`, достает блок `programs[].passing_score` и возвращает структурированный результат;
  - `build_context_entries()` превращает результат инструмента в компактный текстовый контекст для LLM.

В публичном чате вызов происходит здесь:

- `backend/api/routers/chat.py`
  - `_build_public_admission_response()` вызывает `get_passing_scores(...)`, если `classify_admission_tool(...)` вернул `passing_scores`;
  - `_synthesize_public_admission_answer()` собирает `context_entries = build_context_entries(tool_result, ...)` и передает их в prompt;
  - `_assemble_public_admission_response()` возвращает тот же контекст наружу в поле `context`.

Это реализовано как структурированный admission-tool в коде, но не как классический LangChain tool с декоратором `@tool` и не как runtime tool-call LLM. Инструмент выбирается приложением до финального ответа через `classify_admission_tool()`; при недоступном LLM используется fallback по ключевым словам.

## Основной публичный flow

Публичный admission-чат обслуживается отдельными endpoint-ами FastAPI:

- `POST /chat/public/admission`
- `POST /chat/public/admission/stream`

Оба endpoint-а находятся в `backend/api/routers/chat.py` и используют один и тот же внутренний pipeline:

```text
Frontend/Public Web Chat
  -> FastAPI /chat/public/admission
  -> _prepare_public_router_payload()
  -> _run_public_admission_chat()
  -> _build_public_admission_response()
  -> admission_info.py structured tool
  -> format_admission_tool_result()
  -> _synthesize_public_admission_answer()
  -> LLM, если настроен и не нужно пропускать
  -> _assemble_public_admission_response()
  -> analytics save
  -> response.result
```

Streaming endpoint отличается только транспортом ответа: финальный текст режется на `delta`-события SSE, после чего отправляется событие `done` с полным объектом результата.

## Подготовка payload и истории

`_prepare_public_router_payload()`:

- собирает metadata через `_build_analytics_metadata()`;
- выставляет `chat_mode = public_admission`;
- выставляет `auth_mode = anonymous`;
- берет `session_id` из metadata или `uuid`;
- если session есть, подтягивает сохраненную публичную историю из `chat_analytics.fetch_public_session_history(session_id)`;
- объединяет историю из запроса и БД через `_merge_history()`;
- возвращает `router_payload`, metadata, session_id и channel.

История нужна для уточняющих вопросов. Например, если пользователь сначала спросил про конкретную программу, а потом написал "а проходной балл?", код может извлечь программу из истории через `extract_program_with_history()`.

## Выбор admission-инструмента

`_build_public_admission_response()` выполняет основную маршрутизацию внутри admission-домена:

1. Нормализует язык через `normalize_language()`.
2. Загружает данные через `load_admission_data()`.
3. Определяет уровень обучения через `extract_level(query)`.
4. Определяет программу через `extract_program_with_history(query, history, data)`.
5. Определяет список программ через `extract_programs_with_history(...)`.
6. Определяет нужный инструмент через `classify_admission_tool(query, history=history)`.
7. Вызывает одну из функций из `backend/langchain/tools/admission_info.py`.

Основные инструменты:

- `get_available_programs()` для списка программ;
- `get_current_prices()` для стоимости;
- `get_passing_scores()` для проходных/пороговых баллов;
- `get_required_documents()` для документов;
- `get_admission_address()` для адреса;
- `get_admission_contacts()` для контактов;
- `get_study_durations()` для сроков обучения;
- `get_academic_mobility()` и `get_academic_cooperation()` для академической мобильности;
- `get_scholarships()` для грантов и стипендий;
- `get_management()` для руководства.

Если конкретный инструмент не найден, используется обзорный ответ `build_minimal_admission_overview()`. Для конкретных программ обзор сам подтягивает стоимость, проходные баллы и сроки обучения.

## Как выбирается `passing_scores`

`classify_admission_tool()` использует LLM, если он настроен. Если LLM недоступен или вернул неподдерживаемую метку, fallback `detect_requested_tool()` в `backend/langchain/tools/admission_info.py` смотрит на ключевые слова запроса.

В `passing_scores` ведут слова и паттерны вроде:

- `проход`, `балл`, `ент`;
- `score`, `scores`;
- grant-запросы, если они выглядят как вопрос о баллах;
- дополнительные термины из `TOOL_TERMS["passing_scores"]`, включая профильные предметы.

Если запрос одновременно про грант и про баллы, приоритет отдается `passing_scores`, а не `scholarships`.

## Где хранятся пороговые баллы

Источник данных по умолчанию:

```text
backend/data/admission_info.json
```

Путь можно переопределить переменной окружения:

```env
ADMISSION_DATA_PATH=C:\path\to\admission_info.json
```

`load_admission_data()` каждый раз читает JSON из этого пути. Проходные баллы лежат в элементах массива `programs`:

```json
{
  "programs": [
    {
      "name": "...",
      "level": "bachelor",
      "passing_score": {
        "gop_code": "...",
        "grant": 0,
        "grant_full": 0,
        "grant_short": 0,
        "paid": 0,
        "exam": "...",
        "notes": [],
        "updated_at": "2026-04-17"
      }
    }
  ],
  "last_updated": "2026-04-17"
}
```

Фактические поля, которые возвращает `get_passing_scores()`:

- `program`;
- `level`;
- `gop_code`;
- `grant`;
- `grant_full`;
- `grant_short`;
- `paid`;
- `exam`;
- `notes`;
- `profile_subject_1`;
- `profile_subject_2`;
- `updated_at`.

Если уровень обучения не указан, `get_passing_scores()` сначала отфильтровывает программы, где `passing_score` действительно заполнен. Проверка выполняется в `_has_meaningful_passing_score()`.

## Как пороговые баллы попадают в контекст LLM

Для прямого вопроса о баллах цепочка такая:

```text
_build_public_admission_response()
  -> classify_admission_tool(query, history=history) == "passing_scores"
  -> get_passing_scores(program=program, level=level, language=language)
  -> tool_result = {"tool": "passing_scores", "results": [...], ...}
  -> fallback_answer = format_admission_tool_result(tool_result, language)

_synthesize_public_admission_answer()
  -> context_entries = build_context_entries(tool_result, language)
  -> _build_public_admission_ai_prompt(..., context_entries, ...)
  -> llm_client.chat(messages)
```

`build_context_entries()` возвращает список из одного элемента:

```json
[
  {
    "content": "текст, сформированный из результата get_passing_scores()",
    "metadata": {
      "source_path": "...",
      "tool": "passing_scores",
      "data_updated_at": "...",
      "language": "ru"
    }
  }
]
```

Текст в `content` строится через `format_admission_tool_result()`. То есть LLM получает не сырой JSON, а человекочитаемый compact context, сформированный из структурированного результата.

## Когда LLM не используется

LLM пропускается для инструментов:

- `contacts`;
- `address`.

Это задано в `_should_skip_public_admission_llm()`. Для этих инструментов публичный чат возвращает `fallback_answer`, сформированный напрямую из tool-result.

Если `llm_client` не настроен, система также возвращает `fallback_answer`. Для grant-only вопросов есть отдельное сообщение о невозможности сформировать ИИ-ответ.

## Что возвращает публичный admission endpoint

Финальный объект находится в `result` и собирается в `_assemble_public_admission_response()`:

```json
{
  "query": "...",
  "language": "ru",
  "intents": ["admission"],
  "plan": [{"agent": "admission", "description": "Admission Agent"}],
  "trace": [
    {
      "key": "admission",
      "name": "public-admission",
      "description": "Public Admission FAQ",
      "output": {
        "intent": "admission",
        "tool_data": {}
      }
    }
  ],
  "context": [],
  "llm": {
    "used": true,
    "model": "...",
    "error": null,
    "raw_request": null
  },
  "final_answer": "...",
  "tool_data": {}
}
```

Для вопросов о баллах:

- `tool_data.tool` будет `passing_scores`;
- `tool_data.results` будет содержать найденные программы и баллы;
- `context[0].metadata.tool` будет `passing_scores`;
- `final_answer` будет либо LLM-переформулировкой на основе контекста, либо fallback-текстом.

## Отличие публичного чата от приватного agent-router flow

Приватный `/chat/` endpoint идет через `AgentRouter`:

```text
IntentRouterAgent
  -> OrchestratorGraph
  -> AdmissionAgent / PolicyAgent / ...
  -> ResponseAggregator
```

Публичный `/chat/public/admission` не запускает `IntentRouterAgent`, `OrchestratorGraph` и `ResponseAggregator`. Он всегда работает как admission-only FAQ:

```text
public endpoint
  -> LLM admission tool classifier with deterministic fallback
  -> optional LLM synthesis
```

Note: public admission routing now calls `classify_admission_tool(query, history=history)`. If the LLM is unavailable or returns an unsupported label, the classifier falls back to `detect_requested_tool()`.

При этом приватный `AdmissionAgent` в `backend/agents/admission.py` использует тот же классификатор `classify_admission_tool()` и те же функции из `backend/langchain/tools/admission_info.py`: `get_passing_scores()`, `build_context_entries()` и `format_admission_tool_result()`.

## Что считать инструментом в этой кодовой базе

В этой реализации слово "инструмент" означает Python-функцию, которая:

- принимает структурированные параметры (`program`, `level`, `language`);
- читает единый JSON-источник admission-данных;
- возвращает нормализованный dict с полями `status`, `tool`, `results`, `source_path`, `data_updated_at`;
- может быть преобразована в fallback answer и LLM context.

Это не LangChain tool object и не функция, которую модель вызывает через tool calling. Выбор инструмента выполняется приложением до вызова LLM.
