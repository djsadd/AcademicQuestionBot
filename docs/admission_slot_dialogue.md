# Slot-based диалог admission-агента

Admission-пайплайн проверяет обязательные параметры до вызова API/RAG:

```text
Classifier
  -> Request Analyzer
  -> missing slots?
       yes -> Dialogue Manager -> deterministic follow-up -> LLM render
       no  -> AdmissionRequestOrchestrator -> API/RAG -> LLM render
```

Основная реализация:

- `backend/agents/admission_dialogue.py` - конфигурация, извлечение слотов, динамические правила и тексты follow-up;
- `backend/agents/admission.py` - подключение Request Analyzer перед оркестратором;
- `backend/db/chat_analytics.py` - восстановление последнего `admission_state` по `session_id`;
- `backend/api/routers/chat.py` и `backend/telegram_service/polling.py` - передача состояния в следующий запрос.

LLM не решает, хватает ли данных, и не выбирает обязательные поля. Он подключается
после deterministic-решения только как слой формулировки:

- `follow_up` - переформулировать один уточняющий вопрос по `last_requested_slot`;
- `answer` - живо оформить ответ по `fallback_answer`, `tool_result` и `context`;
- если LLM недоступен или вернул пустой ответ, используется deterministic fallback.

## Конфигурация

`SLOT_CONFIG` задаёт обязательные параметры:

```python
{
    "tuition": {"required": ["degree", "program"]},
    "competition": {"required": ["program", "ent_score"]},
    "international": {
        "required": ["citizenship", "degree"],
        "conditional": [
            {
                "when": {
                    "slot": "citizenship",
                    "operator": "is_foreign",
                },
                "required": ["language"],
            }
        ],
    },
    "eligibility": {"required": ["education_level"]},
}
```

Проверка полноты и выбор вопроса выполняются кодом, без LLM.

## Состояние

Каждый ответ содержит:

```json
{
  "admission_state": {
    "domain": "admissions",
    "subdomain": "tuition",
    "slots": {
      "year": 2026,
      "degree": "master",
      "program": null
    },
    "required": ["degree", "program"],
    "missing": ["program"],
    "status": "awaiting_slots",
    "last_requested_slot": "program"
  }
}
```

Состояние сохраняется в `chat_analytics.response_payload`. При следующем запросе оно
восстанавливается по `session_id`. Клиент также может явно передать его в
`context.admission_state`.

Статусы:

- `awaiting_slots` - нужен следующий follow-up;
- `ready` - все параметры собраны, можно вызвать источник;
- `completed` - источник уже вызван.

## Ответ при недостатке данных

До заполнения обязательных слотов:

- `orchestration.api = "dialogue_manager"`;
- `orchestration.tool = "follow_up"`;
- `orchestration.executed = false`;
- `tool_data.status = "needs_clarification"`.

Текст вопроса может быть сгенерирован LLM, но только на основе уже выбранного
`last_requested_slot`. LLM не может добавить новые обязательные поля или вызвать API.

После заполнения слотов `orchestration.executed = true`, а собранные значения
передаются источнику и возвращаются в `tool_data.request_slots`.

В `llm.raw_request` видно, какой слой использовался:

```json
{
  "stages": ["response_render"],
  "render_mode": "answer",
  "fallback_used": false
}
```
