# Пайплайн admission-запроса

Документ описывает текущий пайплайн обработки admission-запросов в проекте: как запрос попадает в `AdmissionAgent`, как выбирается источник данных, когда подключается LLM, как работает оформление заявки и чем отличается публичный admission-чат.

## Основные файлы

- `backend/agents/admission.py` - основной admission-агент для оркестратора.
- `backend/langchain/tools/admission_info.py` - структурированные admission-инструменты и форматирование ответа.
- `backend/data/admission_info.json` - локальная база знаний приемной комиссии.
- `backend/api/routers/chat.py` - HTTP endpoints, включая публичный admission-чат.
- `backend/orchestrator/router.py` - общий роутер агентов.
- `backend/db/admission_applications.py` - сохранение заявок на поступление.

## Общая схема

```text
User message
  -> chat endpoint / Telegram service
  -> AgentRouter
  -> IntentRouterAgent
  -> OrchestratorGraph
  -> AdmissionAgent.run(payload)
  -> application flow или FAQ/info flow
  -> structured admission tool
  -> fallback formatter
  -> LLM render, если доступен и разрешен
  -> AgentResult
  -> ResponseAggregator
  -> client response
```

`AdmissionAgent` возвращает `AgentResult` с:

- `answer` - финальный текст ответа;
- `intent = "admission"`;
- `tool_data` - структурированный результат выбранного admission-инструмента;
- `context` - компактный контекст, построенный из `tool_data`;
- `direct_response` - признак, что оркестратор может остановить дальнейшее выполнение.

## Входной payload

`AdmissionAgent.run(payload)` читает основные поля:

- `message` или `question` - текст запроса пользователя;
- `language` - язык ответа, нормализуется через `normalize_language()`;
- `level` - уровень обучения, если уже известен;
- `program` - образовательная программа, если уже известна;
- `history` - история диалога;
- `telegram_id` или `user_id` - используется при сохранении заявки;
- `person_id` - внутренний идентификатор пользователя, если есть;
- `metadata.channel` - канал запроса.

Если `message` и `question` отсутствуют, агент работает с пустой строкой.

## Шаг 1. Проверка application flow

Первым делом `AdmissionAgent.run()` вызывает:

```python
application_result = _maybe_handle_application_flow(payload, query, language)
```

Если функция вернула `AgentResult`, обычный FAQ/info flow не запускается. Это отдельная ветка для оформления заявки на поступление.

Application flow включается, если:

- текущий запрос содержит trigger-фразы вроде `подать заявку`, `хочу поступить`, `submit application`, `apply for admission`;
- в последних сообщениях истории есть маркеры уже начатого сбора заявки;
- в истории есть маркер готового черновика заявки.

## Шаг 2. Сбор состояния заявки

Состояние заявки восстанавливается из `history` и текущего сообщения через:

```python
_reconstruct_application_state(history, current_query)
```

Агент не хранит промежуточное состояние в отдельной session storage. Он каждый раз восстанавливает прогресс из текста истории.

Поля собираются строго в порядке `APPLICATION_FIELD_ORDER`:

1. `full_name`
2. `iin`
3. `birth_date`
4. `phone`
5. `email`
6. `education_level`
7. `program`
8. `study_language`
9. `study_format`
10. `comment`

Валидация значений выполняется в `_extract_field_value()`:

- ФИО должно содержать минимум 2 слова и быть не короче 5 символов;
- ИИН должен содержать 12 цифр;
- дата рождения принимается в формате `DD.MM.YYYY`, `DD/MM/YYYY` или `DD-MM-YYYY`;
- телефон должен содержать минимум 10 цифр;
- email проверяется регулярным выражением;
- уровень обучения определяется через `extract_level()`;
- программа, язык и формат обучения принимаются как текст;
- комментарий может быть пустым, если пользователь пишет `нет`, `no`, `none`, `-`.

## Шаг 3. Статусы application flow

Application flow возвращает один из статусов в `tool_data.status`:

- `collecting` - агент запрашивает следующее недостающее поле;
- `awaiting_confirmation` - все поля собраны, агент показывает черновик и просит подтверждение;
- `confirm_required` фактически представлен как `awaiting_confirmation` с другим текстом ответа, если пользователь написал не подтверждение и не отмену;
- `cancelled` - пользователь отменил заявку;
- `saved` - заявка сохранена в БД;
- `already_saved` - в этом диалоге заявка уже была сохранена.

Подтверждение распознается по `CONFIRM_TERMS`, например `да`, `ok`, `yes`. Отмена распознается по `CANCEL_TERMS`, например `нет`, `cancel`, `no`.

При подтверждении вызывается:

```python
admission_applications.create_application(...)
```

В таблицу сохраняются контактные данные, уровень обучения, программа, язык/формат обучения, комментарий и технический `payload` с исходным запросом, размером истории и собранными полями.

## Шаг 4. FAQ/info flow

Если заявочная ветка не активна, агент обрабатывает запрос как информационный admission FAQ.

Последовательность:

```python
data = load_admission_data()
level = payload.get("level") or extract_level(query)
history = payload.get("history")
program = payload.get("program") or extract_program_with_history(query, history=history, data=data)
programs = extract_programs_with_history(query, history=history, data=data)
requested_tool = detect_requested_tool(query)
force_ai_answer = _should_force_grant_ai_answer(query)
```

Что происходит на этом этапе:

- `load_admission_data()` читает `backend/data/admission_info.json` или путь из `ADMISSION_DATA_PATH`;
- `extract_level()` определяет уровень обучения из текста;
- `extract_program_with_history()` пытается найти программу в текущем запросе и истории;
- `extract_programs_with_history()` собирает список программ, если в запросе их несколько;
- `detect_requested_tool()` определяет тип вопроса по ключевым словам;
- `_should_force_grant_ai_answer()` отдельно проверяет запросы про гранты.

## Шаг 5. Выбор admission-инструмента

`requested_tool` мапится на одну из функций из `admission_info.py`:

| `requested_tool` | Функция |
| --- | --- |
| `programs` | `get_available_programs()` |
| `prices` | `get_current_prices()` |
| `passing_scores` | `get_passing_scores()` |
| `documents` | `get_required_documents()` |
| `address` | `get_admission_address()` |
| `contacts` | `get_admission_contacts()` |
| `durations` | `get_study_durations()` |
| `academic_mobility` | `get_academic_mobility()` |
| `academic_cooperation` | `get_academic_cooperation()` |
| `scholarships` | `get_scholarships()` |
| `admission_exams` | `get_admission_exams()` |
| `foreign_admission` | `get_foreign_admission_info()` |
| `management` | `get_management()` |
| `student_house` | `get_student_house()` |

Если tool не определен:

- для вопросов про гранты вызывается `get_scholarships()`;
- для остальных запросов собирается обзор через `_build_overview()`, который вызывает `build_minimal_admission_overview()`.

Важно: LLM не выбирает tool сам. Tool выбирается детерминированно Python-кодом через `detect_requested_tool()`.

## Шаг 6. Формирование контекста и fallback-ответа

После выполнения tool-функции агент строит два представления результата:

```python
context_entries = build_context_entries(result, language=language)
fallback_answer = format_admission_tool_result(result, language=language)
```

`context_entries` используется как компактный контекст для LLM. `fallback_answer` используется:

- если LLM не настроен;
- если для tool нужно пропустить LLM;
- если LLM вернул пустой ответ;
- как базовый ответ для application flow.

## Шаг 7. LLM render

Финальный ответ строится через:

```python
_render_admission_answer(...)
```

Логика:

1. Для `contacts` и `address` LLM пропускается всегда, возвращается deterministic fallback.
2. Если `llm_client` не настроен, возвращается fallback.
3. Если это grant-only запрос и LLM не настроен, возвращается специальное сообщение о недоступности AI-ответа.
4. Если LLM настроен, вызывается `_generate_admission_ai_answer()`.
5. Если LLM вернул текст, он становится финальным ответом.
6. Если LLM вернул пустую строку, агент возвращается к fallback.

LLM prompt строится в `_build_admission_ai_prompt()` и содержит строгие правила:

- отвечать только по переданному контексту;
- не придумывать факты;
- при недостатке информации направлять в приемную комиссию;
- не писать формулировки вроде `нет информации`, `не указано`, `no data`;
- для коротких вопросов начинать с прямого ответа;
- возвращать короткий HTML-фрагмент без Markdown;
- если вопрос неоднозначный, задать короткий уточняющий вопрос.

## Особая логика грантов

Запросы про гранты дополнительно проверяются через `_should_force_grant_ai_answer()`. Если запрос похож на вопрос о гранте и обычный tool не определен, агент принудительно берет контекст из `get_scholarships()` и включает режим `grant_only`.

Это нужно, чтобы ответы по грантам были сгенерированы на основе scholarship-контекста, а не через общий обзор.

## Публичный admission endpoint

Публичный admission-чат обрабатывается отдельно в `backend/api/routers/chat.py`:

- `POST /chat/public/admission`
- `POST /chat/public/admission/stream`

Основной flow:

```text
/chat/public/admission
  -> _prepare_public_router_payload()
  -> _run_public_admission_chat()
  -> _build_public_admission_response()
  -> _synthesize_public_admission_answer()
  -> _assemble_public_admission_response()
  -> _save_public_admission_analytics()
```

Публичный flow использует те же admission-инструменты:

- `load_admission_data()`;
- `extract_level()`;
- `extract_program_with_history()`;
- `extract_programs_with_history()`;
- `detect_requested_tool()`;
- `get_*()` функции из `admission_info.py`;
- `format_admission_tool_result()`;
- `build_context_entries()`.

Отличия публичного flow:

- не использует `AdmissionAgent.run()` напрямую;
- не запускает application flow;
- сохраняет аналитику публичного чата;
- поддерживает streaming endpoint, где финальный ответ режется на SSE `delta` chunks;
- дополнительно определяет information gap для слишком общих или неясных публичных вопросов.

## Источник данных admission

`load_admission_data()` читает JSON так:

1. Если задана переменная окружения `ADMISSION_DATA_PATH`, используется она.
2. Иначе используется `backend/data/admission_info.json`.
3. Если файл отсутствует, возвращается структура со статусом `missing_data_file`.
4. Если JSON невалидный, возвращается структура со статусом `invalid_data_file`.

Обновление admission-данных обычно требует изменения только JSON-файла, потому что tool-функции читают его при запросе.

## Где добавлять новую ветку admission-запроса

Для нового типа вопроса обычно нужно:

1. Добавить или расширить данные в `backend/data/admission_info.json`.
2. Добавить tool-функцию или расширить существующую в `backend/langchain/tools/admission_info.py`.
3. Добавить ключевые слова в логику `detect_requested_tool()`.
4. Добавить ветку выбора tool в `AdmissionAgent.run()`.
5. Если это публичный admission-чат, добавить такую же ветку в `_build_public_admission_response()`.
6. Обновить `format_admission_tool_result()` и `build_context_entries()`, если у результата новый формат.

## Диагностика

При проблемах с admission-ответом сначала проверяются:

- какой `requested_tool` вернул `detect_requested_tool(query)`;
- удалось ли извлечь `level` и `program`;
- что лежит в `tool_data`;
- что попало в `context`;
- настроен ли `llm_client`;
- не относится ли tool к `contacts` или `address`, где LLM специально пропускается;
- есть ли нужные данные в `backend/data/admission_info.json`;
- для заявки - корректно ли история содержит предыдущие вопросы и ответы.

