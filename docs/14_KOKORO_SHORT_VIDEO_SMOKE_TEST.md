# Kokoro-ru v2: короткий сквозной video smoke test

**Дата подготовки:** 05.11.2026
**Назначение:** проверить связку production TTS → slides PNG → assemble MP4 на уже озвученном контрольном сценарии.

## Что уже подтверждено

- Production CLI создал 3 WAV через `Kokoro-ru v2 ONNX (CPU)` / `CPUExecutionProvider`.
- Revision: `d649c57`, voice: `dima`.
- WAV: PCM16, mono, 24 000 Hz.
- Manifest: `status=complete`, 3/3 blocks, `quality_warnings=[]`.
- Владелец проекта прослушал все три WAV и подтвердил нормальное звучание.
- `verify_kokoro_assemble_contract.py`: PASS.
- Регрессионные тесты: 76 passed.

## Почему создаётся отдельный script.json

Исходный `data/kokoro_stress_audio_test_script.json` предназначен для проверки речи и содержит 3 блока без описаний слайдов. Подготовщик создаёт отдельную копию в `output/kokoro-production-video-smoke/script.json`, сохраняя ID и `voice_text`, и добавляет по одному простому quote-слайду на блок. Исходный fixture и готовые WAV не изменяются.

В `assets_manifest.json` намеренно записываются пустые списки `broll` и `images`: этот прогон проверяет синхронизацию озвучки и слайдов без сетевого скачивания стоков.

## Команды PowerShell

Из корня `video-farm`:

```powershell
# 1. Подготовить отдельную копию сценария и пустой assets manifest
.\.venv\Scripts\python.exe .\tools\prepare_kokoro_video_smoke.py

# 2. Создать PNG-слайды
.\.venv\Scripts\python.exe -m video_farm.cli slides `
  --script output\kokoro-production-video-smoke\script.json `
  --assets output\kokoro-production-video-smoke\assets_manifest.json `
  --out output\kokoro-production-video-smoke\slides

# 3. Собрать короткое черновое MP4 из уже созданной Kokoro-озвучки
.\.venv\Scripts\python.exe -m video_farm.cli assemble `
  --script output\kokoro-production-video-smoke\script.json `
  --audio-dir output\kokoro-production-smoke `
  --slides-dir output\kokoro-production-video-smoke\slides `
  --assets output\kokoro-production-video-smoke\assets_manifest.json `
  --out output\kokoro-production-video-smoke\kokoro-smoke-draft.mp4 `
  --draft

# 4. Проверить контейнер, потоки, разрешение и длительность
ffprobe -v error `
  -show_entries format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels `
  -of json output\kokoro-production-video-smoke\kokoro-smoke-draft.mp4

# 5. Прочитать отчёт QC
Get-Content .\output\kokoro-production-video-smoke\kokoro-smoke-draft.qc.json -Encoding utf8
```

## Ожидаемое поведение

- В `slides_manifest.json` должны быть 3 PNG-слайда, по одному на каждый ID блока.
- Сборщик должен принять manifest и 3 WAV без ошибок.
- MP4 должен содержать видео 1280×720 и аудио AAC, 44 100 Hz, 2 канала.
- Длительность должна быть около 9,36–9,38 секунды. Небольшое расхождение возможно из-за квантования видеокадров при 25 FPS.
- В `qc.json` ожидаемо появится предупреждение об отсутствии B-roll, поскольку assets manifest намеренно пуст. Также будет предупреждение о длительности вне целевого диапазона 7–9 минут: это короткий технический тест, а не готовый ролик.

## Ручная проверка

Откройте `kokoro-smoke-draft.mp4` и убедитесь, что:

1. последовательно показываются три слайда;
2. фраза на каждом слайде соответствует звучащему WAV-блоку;
3. между блоками нет пропусков, перестановок или заметного рассинхрона;
4. звук присутствует на протяжении всего короткого ролика.

Этот прогон проверяет только сквозную техническую связку и не является приёмкой качества полноценного 7–9-минутного видео.
