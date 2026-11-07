# Запуск нового семантического конвейера на Windows

## Что сохраняется

Старые CLI и модули остаются. Новая команда регистрируется отдельно как `video-farm-semantic`. `.env`, модели Kokoro/RUAccent, `data`, `output`, кэши и резервные каталоги архивом не перезаписываются.

## Установка обновления

Распакуйте overlay ZIP в корень `video-farm`, сохраняя структуру каталогов. Затем из PowerShell:

```powershell
Set-Location "D:\my_projects\AI_Video_Factory_RU\video-farm"
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest tests -q
```

Установка добавит Pydantic v2. Не удаляйте `.venv` и не запускайте переустановку TTS-моделей.

## Таймауты LLM и возобновление планирования

В новом структурированном конвейере основной провайдер получает 120 секунд на ответ, резервный — 900 секунд. Для текущей конфигурации MWS → Ollama это сокращает ожидание перед переключением на локальный Qwen и при этом оставляет локальной CPU-модели до 15 минут. Старый content pipeline сохраняет прежний таймаут 600 секунд. Значения нового конвейера можно переопределить в `.env`:

```dotenv
LLM_PRIMARY_TIMEOUT_SECONDS=120
LLM_SECONDARY_TIMEOUT_SECONDS=900
```

Визуальные планы строятся пакетами по две сцены (`--batch-size 2`). Каждый завершённый пакет атомарно сохраняется в `storyboard_planned.progress.json`. При повторном запуске с тем же входным storyboard уже сохранённые сцены повторно не отправляются моделям. Если исходная раскадровка изменилась, используй новый путь `--out`, чтобы не смешать два разных набора сцен. Пакет `--batch-size 1` уменьшает объём ответа локальной модели ценой большего числа запросов.

## Проверка команды

```powershell
.\.venv\Scripts\python.exe -m video_farm.semantic_cli --help
```

## Полный прогон на существующем сценарии

```powershell
$RunName = "semantic-e2e-2026-11-06"
$RunRoot = Join-Path ".\output\semantic_runs" $RunName

if (Test-Path $RunRoot) { throw "Каталог уже существует: $RunRoot" }

.\.venv\Scripts\python.exe -X utf8 -m video_farm.semantic_cli run `
    --script ".\output\e2e\script.json" `
    --out $RunRoot `
    --name $RunName `
    --speed 0.9 `
    --batch-size 2
```

Новый конвейер обращается к Pixabay. Pexels не вызывается, даже если переменная PEXELS_API_KEY присутствует в `.env`.

## Отдельные этапы

```powershell
# 1. Только смысловая раскадровка
.\.venv\Scripts\python.exe -X utf8 -m video_farm.semantic_cli storyboard `
    --script ".\output\e2e\script.json" `
    --out ".\output\semantic_runs\storyboard_draft.json"

# 2. Визуальная режиссура
.\.venv\Scripts\python.exe -X utf8 -m video_farm.semantic_cli plan `
    --storyboard ".\output\semantic_runs\storyboard_draft.json" `
    --out ".\output\semantic_runs\storyboard_planned.json" `
    --batch-size 2

# 3. Проверка
.\.venv\Scripts\python.exe -X utf8 -m video_farm.semantic_cli validate `
    --script ".\output\e2e\script.json" `
    --storyboard ".\output\semantic_runs\storyboard_planned.json" `
    --out ".\output\semantic_runs\storyboard_validated.json"
```

## Ограничения первой интеграции

- Не подключены платные генераторы изображений/видео.
- Pixabay может вернуть 429/пустые результаты; для проблемной сцены используется внутренний renderer, это отражается в manifest.
- `manual` и `screencast` требуют предоставленный оператором материал.
- Музыка и SFX не скачиваются автоматически.
- `speaker_emotion` — аннотация, не управление эмоцией Kokoro.
- Права на каждый внешний материал и фактические утверждения всё равно должен проверить человек.

Успешный технический QC не является подтверждением редакторского качества и не заменяет просмотр MP4.

## Артефакты полного запуска

В каталоге запуска создаются `storyboard_draft.json`, `storyboard_planned.json`, `storyboard_validated.json`, `storyboard_produced.json`, `media_manifest.json`, `audio/manifest.json`, `publish.json`, `publish.txt`, итоговый MP4, `.assemble.json` и `.qc.json`. Пакет публикации перечисляет реально использованные внешние материалы и факты, требующие человеческой проверки.
