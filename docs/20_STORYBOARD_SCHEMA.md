# Semantic scene schema v1.0

The canonical executable schema is implemented in `src/video_farm/models.py` using Pydantic v2.
LLM response models and Python-owned production models are intentionally distinct.

## Processing ownership

| Fields | Owner |
|---|---|
| `block_id`, `voice_text`, `meaning`, `purpose` | Storyboard LLM; IDs are assigned by Python |
| `visual_type`, `visual_description`, `visual_beats`, `asset_strategy`, `provider_id`, `gen_prompt`, `search_queries`, `on_screen_text`, `speaker_emotion`, `pacing`, `camera_move`, `music_cue`, `audio_sfx[*].name/purpose`, `claims[*].text/source_urls`, `humor_note`, transitions, `chart_data` | Visual planner LLM, locally validated |
| `claims[*].status`, `claims[*].source_availability`, `verified_by_human` | Python/human review; never trusted from LLM |
| SFX source/license/rights state | Python after a real asset and license audit |
| `duration_sec`, `start_sec`, `end_sec` | Python from measured WAV |
| `media_refs.audio`, `media_refs.visuals` | Python only after files exist and hashes are calculated |

## Scene fields

- `id`: stable Python ID, `s_001`, `s_002`, ...
- `block_id`: exact source script block ID.
- `voice_text`: exact contiguous text fragment from the source block.
- `meaning`: semantic point of the fragment.
- `purpose`: role in the narrative.
- `visual_type`: text, diagram, photo, video, scheme, broll, joke, chart, screencast, illustration, quote.
- `visual_description`: detailed composition/action.
- `visual_beats`: optional visual changes without splitting the spoken scene. `sub_duration_ratio` values sum to 1.0.
- `asset_strategy`: stock, rendered, generated, manual, screencast. `generated` is rejected until a provider is configured.
- `provider_id`: extensible provider identifier.
- `gen_prompt`: optional; required by providers that need it.
- `search_queries`: search terms, English preferred for Pixabay.
- `on_screen_text`: short readable labels; 40 characters max.
- `speaker_emotion`, `pacing`, `camera_move`: editorial instructions, not guaranteed Kokoro controls.
- `music_cue`: note only; no auto-download.
- `audio_sfx`: LLM supplies name/purpose only; no automatic source/license claim.
- `claims`: fact claims and candidate URLs. Each claim stays `verify_before_publish` until human review.
- `chart_data`: chart title, equal-length labels/values, unit, source URL and methodology.
- `duration_sec`, `start_sec`, `end_sec`: null until WAV exists.
- `media_refs`: Python-owned audio/visual references with local path, SHA-256, type, provenance and rights state.

## Timing policy

3–25 seconds is the target range. Under 2 seconds and over 30 seconds produce warnings, not forced segmentation. The final edit is built from actual WAV durations.

## Claims and source status

`source_availability` is only an HTTP reachability observation (`not_checked`, `reachable`, `unreachable`). It is not fact verification. Python never promotes claims to `verified`. A human must explicitly approve a claim and set `verified_by_human=true`.

## Chart policy

A chart requires at least two labels and values, identical array lengths, a unit, methodology and a source URL. The renderer plots only those supplied numeric values; no synthetic fallback data is created.

## Реализованные визуальные возможности первой версии

- Для изображений поддерживаются static, slow_zoom, zoom_in, zoom_out, ken_burns и slow_pan.
- Для видео применяется масштабирование/обрезка под 16:9 и длительность речевой сцены.
- Переходы cut и fade реализованы; wipe_left, wipe_right и dissolve пока записываются как предупреждения и собираются hard cut.
- Visual beats монтируются последовательно внутри сцены по долям, сумма которых равна единице.
