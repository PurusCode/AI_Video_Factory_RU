# Kokoro production and short E2E acceptance — 05.11.2026

## Статус

**Принято как короткий технический E2E smoke test.** Это не приёмка полноценного видео и не закрытие этапа 3.

Пользователь подтвердил:
- все три WAV, созданные через production CLI, звучат нормально;
- в коротком MP4 три фразы идут в правильном порядке;
- каждая фраза соответствует отображаемому слайду.

## 1. Production TTS

Команда:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli tts --script data\kokoro_stress_audio_test_script.json --out output\kokoro-production-smoke --speed 0.9
```

Фактическая конфигурация:

- модель: `zaakirio/kokoro-ru`, revision `d649c57`;
- голос: `dima`;
- ONNX Runtime `1.31.0`, `CPUExecutionProvider`;
- Python `3.13.14`, NumPy `2.5.4`;
- RUAccent `1.5.8.3`, Misaki `0.9.4`;
- phonemizer-fork `3.3.2`, espeakng-loader `0.2.4`;
- num2words `0.5.14`;
- скорость `0.9`, threads `2`.

Model SHA-256: `e5bc91f0b15fa85886a82a4fb87e2345fc3de3e6025820a059dde215eb154071`.

Voice pack SHA-256: `e774e8859604164aa27c393fa4393c3a4ff2162d37911a39574551edbc801dcb`.

| ID | WAV | Длительность | Время синтеза | RTF |
|---|---|---:|---:|---:|
| `door_lock` | `01_door_lock.wav` | 2.725 с | 0.818 с | 0.3002 |
| `old_castle` | `02_old_castle.wav` | 3.125 с | 0.844 с | 0.2701 |
| `door_lock_genitive` | `03_door_lock_genitive.wav` | 3.525 с | 1.001 с | 0.2840 |

Manifest: `status=complete`, `blocks_expected=3`, `blocks_completed=3`, `quality_warnings=[]`. Все три WAV: `pcm_s16le`, 24 000 Hz, mono, 16 bit. Длительности совпадают с manifest. Пользователь прослушал все файлы и принял звучание контрольных фраз.

Время по трём строкам синтеза — 2.663 с; средний RTF по блокам — около 0.284. Полное `elapsed_seconds=55.965` включает первичную загрузку ресурсов RUAccent и не должно интерпретироваться как чистое время инференса.

## 2. Regression and assembly input contract

На Windows 05.11.2026 подтверждено:

- `python -m pytest -q`: **76 passed**;
- `doctor`: распознал Kokoro/Dima, ONNX Runtime, RUAccent и локальные assets;
- `verify_kokoro_assemble_contract.py`: `assemble.py manifest contract: PASS`;
- все три WAV прошли входную проверку `assemble.py`.

Эти результаты подтверждают regression suite и входной audio contract, но отдельно не покрывают все сценарии отказа (нет модели, нет ресурсов RUAccent, сбой ONNX-инференса).

## 3. Короткий E2E MP4

Для видео был создан отдельный script JSON с тремя блоками и по одному техническому слайду на блок. Исходный `data/kokoro_stress_audio_test_script.json` и уже созданные WAV не заменялись.

Создание слайдов:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli slides --script output\kokoro-production-video-smoke\script.json --assets output\kokoro-production-video-smoke\assets_manifest.json --out output\kokoro-production-video-smoke\slides
```

Результат: 3 PNG-слайда, RGB. Затем MP4 собран командой `assemble --draft` из этих слайдов и трёх Kokoro WAV.

Фактический `ffprobe` / QC:

| Параметр | Результат |
|---|---|
| MP4 duration | 9.360 с |
| Размер | 839 799 bytes |
| Video | H.264, 1280×720, 25 fps |
| Audio | AAC-LC, 44 100 Hz, 2 channels |
| Timeline | 3 сцены, 3 audio blocks |
| QC critical error | нет |

QC предупреждает об отсутствии B-roll. Это ожидаемо: assets manifest был намеренно пустым, поскольку тест проверял связь TTS, слайдов и сборщика, а не подбор стоков. Длительность также заведомо не соответствует целевым 7–9 минутам.

Пользователь просмотрел MP4 и подтвердил правильный порядок фраз и соответствие каждому слайду.

## 4. Контекстные ударения

`data/kokoro_stress_config.json` содержит одно узкое правило `door_lock_nominative_singular` для контекста «дверной замок». Оно не расширяется на «старый замок» и родительный падеж. Не добавлять regex-правила без отдельного примера ошибочного произношения и последующего прослушивания.

## 5. Что принято и что остаётся открытым

**Принято в рамках короткой технической проверки:**
- production CLI выполняет реальный Kokoro CPU-инференс;
- создаёт 3 WAV и complete manifest;
- WAV соответствует ожидаемому формату и длительности manifest;
- `assemble.py` принимает manifest/WAV;
- три слайда создаются в RGB;
- короткий MP4 собирается, проходит ffprobe/QC и принят пользователем по порядку аудио/слайдов;
- regression suite: 76 passed.

**Не принято / ещё проверить:**
- отдельный production-сценарий с датами, процентами, единицами и крупными числами для проверки `num2words` и `unconverted_numeric_tokens`;
- ошибки при отсутствии модели, ресурсов RUAccent и сбое ONNX;
- полноценный 7–9-минутный ролик на реалистичном проверенном сценарии;
- реальные лицензируемые изображения/B-roll, URL/авторы и publish package;
- визуальная читаемость, разнообразие, монтажный ритм и качество не ниже референсного видео;
- полный просмотр и прослушивание полноценного ролика;
- `THIRD_PARTY_LICENSES.md` на основе фактического production dependency tree до первой производственной публикации.

**Вывод:** техническая интеграция Kokoro и короткий E2E smoke test подтверждены. Этап 3 остаётся в работе; этап 4 «Пилотный контент» не начинается до закрытия критериев MVP.
