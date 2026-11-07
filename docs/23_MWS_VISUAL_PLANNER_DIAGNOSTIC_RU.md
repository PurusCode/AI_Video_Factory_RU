# Диагностика MWS Gemma и Ollama Qwen для visual planner

## Зачем нужен тест

В semantic pipeline это две разные операции:

1. `storyboard.py` — смысловое разделение `voice_text` на сцены. По ранее представленным логам MWS выполнил этот этап: семь запросов завершились с Pydantic validation passed.
2. `visual_planner.py` — визуальная режиссура каждой сцены: тип визуала, описание, стратегия ресурса, промпт, поисковые запросы, надписи, visual beats, claims, chart data и переходы. Именно здесь MWS получал `APITimeoutError`.

Тест изолирует вторую операцию и сравнивает один и тот же вход для `primary` и `secondary`. Дополнительно проверяются простой запрос и поддержка строгого JSON Schema.

## Что проверяется

Для каждого выбранного провайдера:

1. `plain_ping` — короткий запрос без `response_format`. Проверяет базовую доступность endpoint, ключ и генерацию.
2. `tiny_json_schema` — минимальный ответ через `response_format=json_schema`. Проверяет, поддерживает ли шлюз строгий JSON Schema без большой задачи.
3. `visual_single` — настоящий `VisualPlanBatch` по одной исходной сцене `s_001`.
4. `visual_original_pair` — тот же production-контракт и исходная первая пара `s_001`, `s_002`, на которой начинался проблемный запуск.

Visual-запросы выполняются с тем же system prompt, Pydantic JSON Schema, температурой `0.35` и `max_tokens=5000`, что использует production visual planner. Тест не делает repair retry: нам важно записать первый ответ модели без смешивания с результатом повторной генерации.

## Запуск в PowerShell

Из корня `video-farm`:

```powershell
.\.venv\Scripts\python.exe -X utf8 .\tools\diagnose_visual_planner.py `
    --storyboard ".\output\semantic_runs\first-semantic-e2e\storyboard_draft.json" `
    --providers primary,secondary
```

Путь к `storyboard_planned.json` тоже допустим: скрипт отправляет моделям только исходные поля сцены (`id`, `block_id`, `voice_text`, `meaning`, `purpose`) и не передаёт уже созданные визуальные решения обратно в prompt.

Таймауты по умолчанию:

- короткая проверка: 30 секунд;
- минимальная JSON Schema проверка: 45 секунд;
- visual planner primary: 180 секунд;
- visual planner secondary: 420 секунд.

Их можно изменить аргументами `--probe-timeout`, `--schema-probe-timeout`, `--primary-visual-timeout`, `--secondary-visual-timeout`. Для отдельной проверки только MWS укажи `--providers primary`.

## Где искать результаты

Скрипт создаёт два новых файла в `output/diagnostics/visual-planner-provider/`:

- JSON — подробный отчёт, включая raw-ответы, ошибки, `finish_reason`, usage/tokens, время, хэши system prompt, prompt и схемы;
- Markdown — краткая таблица статусов.

Скрипт не изменяет `storyboard_draft.json`, `storyboard_planned.json`, checkpoint, `.env` или production-код. API-ключи в отчёты не записываются.

## Как интерпретировать

| Результат | Вывод |
|---|---|
| `plain_ping` timeout/error | Проблема базовой доступности endpoint, сети, ключа или сервиса; пока нельзя делать вывод о качестве модели. |
| `plain_ping=ok`, `tiny_json_schema` format unsupported | Базовая генерация работает, но режим строгой схемы не поддержан так, как ожидает адаптер; надо проверять fallback-формат. |
| `tiny_json_schema=ok`, `visual_single=timeout` | Шлюз и строгий JSON работают; тормозит именно задача визуального планирования/большая схема/генерация ответа. |
| `visual_single=pydantic_valid`, `visual_original_pair=timeout` | Одна сцена помещается в окно запроса, а пара сцен — нет; нужно уменьшать batch size или объём схемы/промпта. |
| `visual_single=pydantic_invalid` | Модель отвечает, но первый ответ не соответствует локальному Pydantic-контракту. Подробности указаны в `validation_error`. |
| обе модели `pydantic_valid` | Сравнивать raw-результаты по смысловой точности, разнообразию и достоверности, а не только по времени. |

Таймаут означает только то, что endpoint не вернул ответ за заданный срок. Это не доказывает, что у модели недостаточно знаний или способностей. Число параметров также не гарантирует, что конкретный API deployment будет быстрее или лучше на structured-output задаче.

## Важное ограничение

Этот тест — диагностический benchmark одного и того же короткого примера, а не полный бенчмарк качества на всех 43 сценах. Он отвечает на вопрос, почему текущий вызов primary не завершался: базовый endpoint, строгий JSON Schema, одиночная сцена или первая пара сцен. Для сравнительной оценки качества понадобится отдельно экспертно оценить одинаковые принятые планы обоих провайдеров.
