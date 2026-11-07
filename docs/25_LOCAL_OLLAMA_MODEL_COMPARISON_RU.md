# Сравнение дополнительных локальных моделей Ollama

## Цель

Проверить `frob/qwen3.5-instruct:27b` и `frob/qwen3.5-instruct:latest` на той же
задаче visual planner, что и Qwen 2.5 14B и MWS Gemma 4 31B. Производственный
маршрутизатор моделей не меняется.

## Идентичность моделей

В каталоге Ollama `frob/qwen3.5-instruct:27b` опубликована как 27.8B, Q4_K_M,
размер около 17 GB. `frob/qwen3.5-instruct:latest` отображается размером 6.6 GB
и имеет тот же digest, что тег `:9b`; это не вторая 27B-модель.

Публикатор описывает этот репозиторий как non-thinking варианты Qwen3.5. Это
необходимо учитывать при интерпретации результатов: эксперимент сравнивает
именно эти Ollama-теги, а не все варианты архитектуры Qwen3.5.

## Ограничения 32 GB RAM

17 GB — размер скачиваемых весов, а не полное потребление RAM. Дополнительно
нужны память для KV cache, runtime Ollama, Windows и других процессов. При
CPU-only запуске 27B Q4 может поместиться в 32 GB, но запас ограничен. Поэтому
диагностический тест задаёт `num_ctx=8192`; максимальное окно 256K из карточки
модели не используется. Закрой тяжёлые приложения и наблюдай за доступной
памятью Windows. Если система начинает активно использовать файл подкачки,
останови тест и сначала проверь модель 9B.

## Методика

1. `secondary` — контрольный Qwen 2.5 14B из существующего `.env`.
2. `frob/qwen3.5-instruct:27b` и `:latest` — дополнительные теги, использующие
   тот же локальный endpoint из `LLM_SECONDARY_BASE_URL`.
3. Все модели получают один и тот же system prompt, пользовательский prompt,
   `VisualPlanBatch` JSON Schema, `temperature=0.35`, `max_tokens=5000` и один
   вход `s_001`.
4. Для localhost в запросе задаётся `options.num_ctx=8192`.
5. Сохраняются raw output, finish_reason, usage, latency и результат локальной
   Pydantic-валидации. Автоматический repair retry не выполняется.
6. Сначала тестируется одна сцена. Пару сцен запускать только после анализа
   результата одиночной сцены.

## Команда

```powershell
.\.venv\Scripts\python.exe -X utf8 .\tools\diagnose_visual_planner.py `
  --storyboard ".\output\semantic_runs\first-semantic-e2e\storyboard_draft.json" `
  --providers secondary `
  --ollama-models "frob/qwen3.5-instruct:27b,frob/qwen3.5-instruct:latest" `
  --visual-cases single `
  --visual-formats json_schema_strict `
  --ollama-visual-timeout 900 `
  --ollama-num-ctx 8192 `
  --visual-max-tokens 5000
```

## Интерпретация

- `pydantic_valid` — ответ корректен по локальному контракту `VisualPlanBatch` и
  содержит именно запрошенные scene IDs.
- `pydantic_invalid` — ответ получен, но не прошёл локальную схему.
- `invalid_json` — не удалось разобрать JSON.
- `timeout` — модель не ответила за заданное время; это не доказательство
  неспособности выполнить задачу.

Успех по схеме не равен качеству режиссуры. После технической валидации отдельно
оцениваются смысловое соответствие voice_text, выполнимость visual description,
разнообразие, отсутствие выдуманных чисел и качество поиска визуальных активов.
