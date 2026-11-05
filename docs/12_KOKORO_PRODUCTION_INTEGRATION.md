# Kokoro-ru v2 production integration — implementation package

<!-- KOKORO_HISTORICAL_STATUS_NOTE_2026-11-05 -->
> **Историческая пометка (05.11.2026):** этот документ фиксирует состояние проекта до последующих проверок 05.11.2026. После него были выполнены production-проверки Kokoro на целевой Windows-машине и короткая E2E-приёмка MP4. Актуальные результаты и границы приёмки описаны в `docs/14_KOKORO_SHORT_VIDEO_SMOKE_TEST.md` и `docs/15_KOKORO_SHORT_E2E_ACCEPTANCE.md`. Исторические результаты ниже сохранены и не должны трактоваться как текущий статус.


**Target:** `video-farm` production CLI
**Engine:** `zaakirio/kokoro-ru`, pinned revision `d649c57`, voice `dima`
**Runtime:** ONNX Runtime / `CPUExecutionProvider`
**Status:** code integration package; Windows installation and real CLI/E2E acceptance are still required.

## 1. What this package changes

- Replaces the production Piper synthesis implementation with Kokoro-ru v2 Dima.
- Keeps the public call `synthesize(settings, script_path, out_dir, speed=...)`.
- Preserves one WAV per script block and `audio/manifest.json`.
- Keeps the manifest fields consumed by `assemble.py`: `blocks[].id`, `blocks[].file`, and `blocks[].duration_seconds`.
- Adds provenance: repository/revision, model and voice SHA-256, config/G2P hashes, RUAccent stress-config hash, runtime versions, CPU provider, speed and thread count.
- Writes partial manifest progress after each completed block and `status=failed` with error details on failure.
- Does not fall back to Piper. A missing dependency, model, RUAccent asset, G2P symbol or ONNX error fails visibly.
- Updates the `.env.example`, installer, dependencies, doctor diagnostics, CLI help/progress and README.

## 2. Runtime asset locations

Model snapshot is downloaded on the first TTS run into:

`data/models/kokoro-ru-v2-onnx/`

The code downloads only the pinned Dima model and its required frontend files from revision `d649c57`. The weights and voice pack are not part of this archive and must not be committed to public GitHub.

RUAccent data is expected at:

`data/models/ruaccent-accentuator/`

Required subdirectories:

- `dictionary/`
- `nn/nn_accent/`
- `nn/nn_stress_usage_predictor/`
- `nn/nn_yo_homograph_resolver/`

The integration deliberately does not invent a download procedure for RUAccent assets. The existing benchmark setup used a prepared local RUAccent model directory. If that directory is absent, `doctor` and production TTS report a clear error rather than silently initializing an unpinned or differently located accent model. Keep the benchmark assets and production assets in the same project-local directory.

Contextual stress rules remain in `data/kokoro_stress_config.json`.

## 3. Installation on Windows

Run from the repository root after extracting the archive:

```powershell
py -3.13 .\tools\apply_kokoro_integration_patch.py
```

The patch script updates the existing `cli.py` and `README.md` in place. It checks every expected anchor and stops if the repository files differ from the reviewed baseline. It does not overwrite the rest of those files.

Then install the production dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[tts,test]"
```

If `.venv` does not exist, run:

```powershell
.\install.ps1
```

Check configuration in `.env`:

```dotenv
TTS_ENGINE=kokoro
TTS_LANGUAGE=ru
TTS_SPEAKER=dima
TTS_SPEED=0.9
KOKORO_THREADS=2
```

Do not add model weights, voice pack, RUAccent data or `.env` to Git.

## 4. Validation sequence

First inspect the environment:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli doctor
```

`doctor` checks Kokoro runtime packages, RUAccent local data and stress configuration. The pinned Kokoro ONNX snapshot is downloaded by the first TTS command if it is not already cached.

Run focused and full tests:

```powershell
$env:PYTHONPATH = ".\src"
.\.venv\Scripts\python.exe -m pytest -q tests\test_tts_pipeline.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests tools
```

Run the production CLI against the existing control script:

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli tts --script data\kokoro_stress_audio_test_script.json --out output\kokoro-production-smoke --speed 0.9
```

Inspect the manifest:

```powershell
$m = Get-Content -Encoding utf8 .\output\kokoro-production-smoke\manifest.json -Raw | ConvertFrom-Json
$m | Select-Object status, engine, engine_version, repository, revision, voice, speed, threads, total_duration_seconds, elapsed_seconds
$m.blocks | Select-Object id, file, duration_seconds, sample_rate, channels, unconverted_numeric_tokens
```

Expected:
- `status = complete`;
- `engine = Kokoro-ru v2 ONNX (CPU)`;
- `revision = d649c57`;
- `voice = dima`;
- all expected blocks have WAV files at 24 kHz mono PCM16;
- no block is missing from the manifest.

Listen to every generated WAV. Do not treat a successful CLI exit or a valid manifest as editorial acceptance.

## 5. Assembler and full E2E

The assembler remains unchanged. It validates every WAV and verifies that the manifest covers all script block IDs and that declared durations match the actual WAV files.

After TTS smoke test, run the normal pipeline with a known-good script and available assets/slides. Verify:
- final MP4 exists and is playable;
- FFprobe QC is successful;
- audio and visuals remain synchronized;
- every block is audible and no block is missing;
- no clipping, unexpected pauses, or pronunciation/stress defects are present.

The E2E render and manual listening/viewing are not performed by extracting this archive. Stage 3 must remain open until these checks pass on the target Windows machine.

## 6. Dependency and licensing notes

The `[tts]` extra pins the direct runtime packages and Git revisions used by the production engine. The separate `requirements-kokoro-py313.lock.txt` remains the isolated benchmark environment lock; it is not asserted to be a fully audited production lock.

Before the first distributable production build, generate and review `THIRD_PARTY_LICENSES.md` against the actual installed production dependency tree. This package does not claim that legal notices or the §3 Dialogs OpenRAIL residual risk have been resolved. The decision in `docs/11_KOKORO_PRODUCTION_AND_LICENSE_DECISION.md` remains authoritative.

## 7. Explicit non-goals

- No Piper fallback or Piper selection.
- No distribution of model weights, voice pack or RUAccent model data.
- No claim that the full video pipeline has passed E2E.
- No automatic upload or publication to VK Video / RuTube.
- No automatic closure of Stage 3.
