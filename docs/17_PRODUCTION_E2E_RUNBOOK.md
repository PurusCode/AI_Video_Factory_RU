# Runbook: полный производственный E2E на Windows

- **Версия:** 1.0
- **Дата:** 06.11.2026
- **Назначение:** пошаговый запуск одного полного ролика 7–9 минут на текущем CLI `video-farm`.
- **Статус:** инструкция; команды ещё не запускались в рамках этого документа.

## 0. Важные правила

- Работать из корня репозитория `D:\my_projects\AI_Video_Factory_RU\video-farm`.
- Использовать существующее production-окружение `.venv`, не benchmark `.kokoro-venv`.
- Не удалять каталоги моделей, RUAccent, кэши и существующие результаты.
- Не публиковать `.env`, API-ключи, веса модели или полный датасет.
- Для финального MP4 не добавлять флаг `--draft`.
- Перед `run` сценарий должен быть вручную проверен и утверждён.
- CLI `run --script-file` использует готовый JSON и пропускает генерацию сценария/LLM; затем последовательно выполняет TTS → assets → slides → assemble/QC → описание.

## 1. Подготовить параметры запуска

Открой PowerShell и перейди в репозиторий:

```powershell
Set-Location D:\my_projects\AI_Video_Factory_RU\video-farm
```

Задай уникальные имя и пути (имя меняй для каждого нового прогона):

```powershell
$RunName = "production-e2e-2026-11-06"
$ScriptPath = "output\e2e\script.json"
$RunRoot = "output\runs\$RunName"
$VideoPath = "$RunRoot\$RunName.mp4"

New-Item -ItemType Directory -Force -Path ".\output\e2e" | Out-Null
```

Проверь, что `$RunRoot` ещё не содержит результаты прошлого запуска. Не перезаписывай принятый прогон: используй новое уникальное имя.

## 2. Preflight

### 2.1. Ветка и коммит

```powershell
git status -sb
git rev-parse HEAD
git log -1 --oneline
```

Зафиксируй SHA коммита в отчёте. Если есть незакоммиченные изменения кода, не смешивай их с тестом: сначала выясни их назначение и зафиксируй состояние.

### 2.2. Диагностика и тесты

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli doctor

$env:PYTHONPATH = ".\src"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests tools
.\.venv\Scripts\python.exe -m pip check
```

Ожидается успешный `doctor`, успешный compileall, `pip check` без сломанных зависимостей и прохождение тестов. Последний известный baseline — 82 passed; если актуальный прогон даст другое число, записать фактическое значение и расследовать падения, не подгонять документацию под ожидаемую цифру.

`doctor` должен подтвердить Kokoro/Dima, ONNX Runtime CPU, кэш модели, конфигурацию ударений и локальные RUAccent assets. Важное различие: модель Kokoro и RUAccent assets — два разных набора. Наличие одного не доказывает наличие другого.

## 3. Подготовить тему и источники

Есть два допустимых маршрута.

### Маршрут A — через Discovery

Если настроен YouTube API и есть доступный дневной бюджет:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli discover --out output\discovery
.\.venv\Scripts\python.exe -m video_farm.cli discover-quota
```

Изучи `output\discovery\discovery.md` и `discovery.json`. Выбери тему вручную. При необходимости создай локальную панель:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli discover-editor --input output\discovery\discovery.json --out output\discovery
```

Открыть `output\discovery\editor.html` в браузере. Панель предназначена для локального отбора и не запускает новый YouTube API-запрос при открытии.

Не используй старую команду `analyze`: она отключена. Не интерпретируй общее число просмотров как скорость роста.

### Маршрут B — ручная тема

Можно выбрать тему вручную, не выполняя Discovery. В этом случае отдельно подготовь ссылки на первичные/надёжные источники для всех значимых фактов сценария.

## 4. Создать черновик сценария

Заполни реальную тему вместо примера:

```powershell
$Topic = "ВСТАВЬТЕ СОГЛАСОВАННУЮ ТЕМУ"

.\.venv\Scripts\python.exe -m video_farm.cli script `
    --topic $Topic `
    --out $ScriptPath `
    --min-words 1100
```

Параметр `--min-words 1100` — стартовый нижний порог, не гарантия длительности 7–9 минут.

Проверь, что JSON читается:

```powershell
.\.venv\Scripts\python.exe -m json.tool $ScriptPath > $null
if ($LASTEXITCODE -ne 0) { throw "script.json не является корректным JSON" }
```

## 5. Ручная проверка и утверждение сценария

Открой `output\e2e\script.json` и проверь до запуска полного pipeline:

1. У каждого блока есть стабильный уникальный `id`.
2. Сюжет имеет вступление, развитие, переходы, вывод и не содержит повторов ради хронометража.
3. Все значимые утверждения проверены по независимым источникам. Ссылки и результаты проверки записаны.
4. `text` подходит для экрана; `voice_text` предназначен для естественного произношения.
5. Числа, даты, единицы, валюты, термины и аббревиатуры написаны однозначно для TTS.
6. Слайды и визуальные ключевые слова описывают именно то, о чём говорит соответствующий блок.
7. `fact_checks` и `quality_warnings` просмотрены. Наличие этих полей само по себе не доказывает фактчекинг.
8. Структура и содержание соответствуют ожидаемому качеству; нет искусственного растягивания текста.

Если редактировал сценарий, повторно проверь JSON:

```powershell
.\.venv\Scripts\python.exe -m json.tool $ScriptPath > $null
if ($LASTEXITCODE -ne 0) { throw "После редактирования script.json повреждён" }
```

Только после ручного утверждения скопируй сценарий в каталог конкретного запуска. Так в результатах сохранится точная версия сценария, использованная при производстве.

```powershell
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$ApprovedScriptPath = Join-Path $RunRoot "script.json"
Copy-Item -LiteralPath $ScriptPath -Destination $ApprovedScriptPath
$ScriptPath = $ApprovedScriptPath
```

## 6. Проверить ключи внешних сервисов

Для генерации сценария нужен доступный LLM provider. Для реального поиска и скачивания фото/B-roll должны быть настроены `PEXELS_API_KEY` и/или `PIXABAY_API_KEY` в локальном `.env`.

Не выводи содержимое `.env` в консоль и не присылай API-ключи в чат.

Без ключей стоков модуль может создать manifest с пустыми списками и предупреждением. Такой результат не закрывает критерий реальных лицензируемых визуалов для полного E2E.

## 7. Полный pipeline по утверждённому JSON

Запусти:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli run `
    --script-file $ScriptPath `
    --name $RunName `
    --speed 0.9 `
    --max-keywords 30
```

**Не добавляй `--draft`.** Это полный рендер.

Команда создаёт каталог `output\runs\$RunName` и последовательно выполняет:

1. использование утверждённого сценария без LLM-генерации;
2. TTS Kokoro Dima;
3. поиск/загрузку медиа и `assets_manifest.json`;
4. создание PNG-слайдов и `slides_manifest.json`;
5. полный монтаж MP4 и FFprobe/QC;
6. `publish.txt`/`publish.json` на основе результата и фактически использованных медиа.

Если команда завершается ошибкой, не запускай монтаж по частичным или старым артефактам. Сохрани лог и выясни, какой этап завершился неудачно.

## 8. Проверить аудиоманифест и длительность

```powershell
$AudioManifestPath = Join-Path $RunRoot "audio\manifest.json"
$audio = Get-Content -LiteralPath $AudioManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

$audio | Select-Object status, blocks_expected, blocks_completed, total_duration_seconds
$audio.blocks | Select-Object id, file, duration_seconds, unconverted_numeric_tokens
```

Критерии:

- `status` равен `complete`;
- `blocks_expected` равен `blocks_completed`;
- для каждого `id` существует WAV;
- нет пустых/повреждённых WAV;
- WAV соответствует PCM16 mono 24 kHz;
- измеренные длительности согласуются с manifest;
- сумма длительностей — от 420 до 540 секунд;
- `unconverted_numeric_tokens` пусты либо каждый оставшийся токен отдельно разобран, исправлен/одобрен и прослушан.

Прослушай всю озвучку от начала до конца. Нельзя ограничиваться одним контрольным блоком.

## 9. Проверить визуалы и слайды

Открой `assets_manifest.json`, `slides_manifest.json` и каталог `$RunRoot\slides`. В текущей конфигурации `assets.py` сохраняет B-roll в `data\broll`, а фотографии — в `data\images`; это общие каталоги проекта, а не подпапки `$RunRoot`. Точные пути к скачанным файлам указаны в полях `file` манифеста.

Проверь:

- реальные файлы существуют и воспроизводятся/открываются;
- визуалы соответствуют смысловым блокам;
- слайды не содержат обрезанного, слишком мелкого или ошибочного текста;
- нет нерелевантного B-roll;
- каждый внешний материал, использованный в timeline, имеет проверяемую исходную страницу и сведения об авторе/условиях использования;
- не путай все найденные материалы с теми, которые реально попали в ролик.

## 10. Проверить MP4 и QC

```powershell
$QCPath = [System.IO.Path]::ChangeExtension($VideoPath, ".qc.json")
$qc = Get-Content -LiteralPath $QCPath -Raw -Encoding UTF8 | ConvertFrom-Json

$qc | Select-Object file, draft, duration_seconds, duration_minutes, size_bytes
$qc.video | Format-List
$qc.audio | Format-List
$qc.warnings
$qc.used_media | Format-Table -AutoSize
```

Критерии:

- `draft` равен `false`;
- длительность — 420–540 секунд;
- видео 1920×1080, 25 fps, H.264 High, yuv420p;
- аудио AAC, 44.1 kHz, 2 канала;
- битрейт и прочие фактические параметры сверены с целевым профилем и требованиями площадки;
- нет неразрешённых критических warnings;
- `used_media` отражает файлы, реально присутствующие в timeline.

Дополнительная независимая проверка:

```powershell
ffprobe -v error `
    -show_entries format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate,profile,pix_fmt,sample_rate,channels,bit_rate `
    -of json $VideoPath
```

Если итоговый путь отличается, возьми его из вывода команды `run`.

## 11. Проверить пакет публикации

В `$RunRoot` должны находиться `publish.txt` и `publish.json`. Проверь:

- описание соответствует ролику;
- хэштеги релевантны и не вводят в заблуждение;
- указаны именно фактически использованные внешние материалы;
- нет неиспользованных стоков, выданных за использованные;
- нет неизвестной/непроверенной атрибуции, замаскированной под подтверждённую;
- все предупреждения рассмотрены.

Проверь лицензию и исходную страницу каждого материала из `used_media`. Автоматически сформированный attribution-текст сам по себе не является юридическим заключением.

## 12. Полный просмотр и ручная приёмка

Просмотри MP4 полностью в обычном видеоплеере. Отдельно прослушай всю дорожку без ускорения.

Проверь:

- соответствует ли голос визуалу на каждом смысловом отрезке;
- не появляются ли неподходящие изображения/видеоклипы;
- не остаются ли пустые, слишком долгие или повторяющиеся сцены;
- читаются ли надписи на обычном экране;
- естественны ли ударения, числительные, паузы и произношение терминов;
- корректны ли переходы и финал;
- не уступает ли общий результат референсу владельца проекта.

Зафиксируй все замечания с таймкодами. При блокирующем замечании сценарий/медиа/слайды исправляются, после чего прогон повторяется с новым именем каталога.

## 13. Сохранить отчёт и закрыть/не закрыть тест

Скопируй шаблон `docs\18_PRODUCTION_E2E_ACCEPTANCE_TEMPLATE.md` в каталог прогона, например:

```powershell
Copy-Item .\docs\18_PRODUCTION_E2E_ACCEPTANCE_TEMPLATE.md `
    (Join-Path $RunRoot "E2E_ACCEPTANCE_REPORT.md")
```

Заполни фактические значения, ссылки на источники, результаты QC, оценку владельца и решение PASS/CONDITIONAL PASS/FAIL.

Не отмечай этап 3 завершённым только по факту создания MP4. Для закрытия этапа нужны все exit criteria из `docs/03_roadmap.md`, включая отказные тесты, `THIRD_PARTY_LICENSES.md` и полноту publish package.
