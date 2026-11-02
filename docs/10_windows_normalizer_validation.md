# Windows-приёмка автоматической нормализации TTS

**Версия:** 1.1  
**Дата:** 26.10.2026  
**Статус:** реальный `num2words 0.5.14` запускался на Windows с нормализатором v0.2.1; выявлены недочёты рода. Патч v0.2.2 ожидает повторной приёмки на Windows.

Эта проверка подтверждает не просто наличие кода нормализатора, а фактическое поведение установленного `num2words`, нормализованный текст в манифестах и получившийся WAV. Она не заменяет субъективную оценку тембра/естественности и лицензионную приёмку TTS.

## 1. Обновить основное окружение Piper

PowerShell должен быть открыт в корне `video-farm`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[tts,test]"
.\.venv\Scripts\python.exe -m video_farm.cli doctor
.\.venv\Scripts\python.exe -m pytest -q tests\test_text_normalization.py -rs
```

Ожидается:

- `doctor` показывает `Числовая нормализация TTS: OK (num2words 0.5.14)` (или текущую версию в разрешённом диапазоне);
- интеграционный тест `test_real_num2words_ru_cases_when_installed` выполняется и проходит, не `skipped`;
- интеграционный test показывает, как настоящая версия `num2words` преобразует контрольные конструкции. Русская локаль 0.5.14 поддерживает как короткие коды `n/g/d/a/i/p`, так и английские aliases; в проекте выбраны короткие коды для единообразия.

## 2. Быстро посмотреть нормализованный текст

```powershell
.\.venv\Scripts\python.exe -c "from video_farm.text_normalization import normalize_for_speech; print(normalize_for_speech('Дата 16.10.2026; в 14:35; погрешность 3,7%; температура 21,5 градуса; файл 1,25 ГБ; стоимость 4 500 рублей.'))"
```

Проверь глазами, что результат читается по-русски и использует согласованные словесные формы. Для v0.2.1 уже была зафиксирована проблема с женскими существительными; поэтому дополнительно проверь команду из раздела 3 ниже. Это ограниченный набор тестов, не полный морфологический анализ русского языка.

## 3. Регрессионная проверка грамматического рода и пунктуации (v0.2.2)

После применения патча выполнить:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_text_normalization.py -rs
.\.venv\Scripts\python.exe -c "from video_farm.text_normalization import normalize_for_speech; print(normalize_for_speech('Осталась 1 минута. Через 2 минуты начнём. Длительность — 21 секунда. Затем подождите 22 секунды. Встреча в 14:02. Температура — 21 градус, затем 21,5 градуса.'))"
```

Проверяемые ожидаемые фрагменты: `одна минута`, `две минуты`, `двадцать одна секунда`, `двадцать две секунды`, `четырнадцать часов две минуты`, `Температура — двадцать один градус`. Тире должно сохраниться, а не превращаться в запятую. Десятичная дробь должна оставаться в форме `двадцать одна целая пять десятых градуса` (грамматически формальная, но допустимая форма). Если локальный `num2words` даёт другое словоизменение — сохранить фактический вывод и исправить правила на основе реального API, а не моков.

Это ограниченный набор покрытых шаблонов, а не полное согласование русского предложения по синтаксису. Контекст вида `файл 1,25 ГБ` может требовать редакторского `voice_text` («размер файла — ...»).

## 4. Установить normalizer dependency для Kokoro

`.kokoro-venv` изолировано от основного `.venv`, поэтому установить пакет нужно отдельно:

```powershell
.\.kokoro-venv\Scripts\python.exe -m pip install "num2words>=0.5.14,<0.6"
```

## 5. Запустить общий benchmark на обоих движках

Используйте один JSON, не редактируйте его между прогонами:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli tts --script data\tts_quality_benchmark_script.json --out output\piper-benchmark-normalizer-v022 --speed 1.0

.\.kokoro-venv\Scripts\python.exe -X utf8 .\tools\kokoro_onnx_benchmark.py --script data\tts_quality_benchmark_script.json --out output\kokoro-benchmark-normalizer-v022 --voice dima --threads 2
```

Ожидается, что обе команды закончатся успешно и сохранят WAV и `manifest.json`. Если появилась ошибка, сохранить весь traceback и не удалять `status=failed` manifest.

## 6. Проверить манифесты и предупреждения

Для Piper:

```powershell
$m = Get-Content -Encoding utf8 .\output\piper-benchmark-normalizer-v022\manifest.json -Raw | ConvertFrom-Json
$m | Select-Object status, text_normalizer_version, text_normalizer_backend
$m.blocks | Select-Object id, source_voice_text, normalized_voice_text, unconverted_numeric_tokens, file
```

Для Kokoro:

```powershell
$k = Get-Content -Encoding utf8 .\output\kokoro-benchmark-normalizer-v022\manifest.json -Raw | ConvertFrom-Json
$k | Select-Object status, text_normalizer_version, text_normalizer_backend, revision, voice
$k.blocks | Select-Object id, source_voice_text, normalized_voice_text, unconverted_numeric_tokens, file
```

Критерии:

1. `status` — `complete`.
2. `text_normalizer_backend` указывает установленную версию `num2words`, а не `UNAVAILABLE`.
3. Поддерживаемые тестовые даты, время, проценты, величины/валюты преобразованы корректно.
4. `unconverted_numeric_tokens` пуст только если в исходном сценарии действительно не осталось неизвестных цифровых форм. Если токены есть — не скрывать предупреждение; либо поправить `voice_text` вручную, либо расширить нормализатор с отдельным регрессионным тестом.
5. Прослушать соответствующие WAV обоих движков. Ручная преднормализация показала, что словесная форма может исправить числа, но не снимает проблем естественности, окончаний и ударений.

## 7. Приёмка и статус

После теста записать в `docs/08_tts_quality_benchmark.md` результаты:

- реальная версия `num2words` и вывод интеграционного теста;
- корректность `normalized_voice_text` для каждого блока;
- список оставшихся цифровых токенов;
- мнение пользователя по числам, окончаниям, ударениям, паузам и естественности отдельно для каждого голоса;
- длительность WAV и время синтеза.

Не повышать текущие оценки автоматически: Kokoro Dima — 3,5/5, Piper Dmitri — 2,5/5. Производственная модель не выбрана, пока естественность не достигнет ≥4/5 и не будут закрыты лицензионные блокеры.
