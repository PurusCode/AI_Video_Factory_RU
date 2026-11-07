# ADR-19 — Semantic Storyboard Architecture

**Version:** 1.0
**Date:** 2026-11-06
**Status:** Accepted as target architecture; implementation is staged in the semantic pipeline.

## Context

The legacy production path is block-oriented: a script block has a long `voice_text`, static slide rows and stock keywords. TTS creates one WAV per block. The legacy assembler allocates the block's duration between slide images and inserts short stock clips. This cannot guarantee that the displayed visual corresponds to the exact sentence currently being spoken.

## Decision

1. The primary editorial unit is a **semantic scene**, not a slide or a script block.
2. Every scene contains an exact contiguous `voice_text` excerpt from one source block.
3. Storyboard generation is a separate LLM step from visual planning.
4. A Python coverage validator rejects omissions, duplicates, reordering, paraphrasing and cross-block leakage.
5. Visual planning is a second LLM step. It may select stock from Pixabay or locally rendered graphics. Paid image/video generation APIs are not enabled in the first iteration.
6. TTS produces one WAV per scene using the existing pinned Kokoro-ru v2 Dima ONNX CPU engine.
7. Scene duration is measured from the WAV. `start_sec` and `end_sec` are accumulated from measured durations, never estimated by dividing a block into equal slide intervals.
8. `visual_beats` allow multiple visual shots inside one continuous speech scene. Their ratios must total 1.0.
9. `claims[]` are tracked individually. URL reachability is separate from factual verification. No automated HTTP check can set a claim to `verified`.
10. New modules are additive. Legacy `slides.py`, `assemble.py`, `tts.py`, and `cli.py` remain available until the new pipeline passes Windows acceptance.

## Component boundaries

| Module | Responsibility |
|---|---|
| `storyboard.py` | Split the source narration into exact semantic excerpts |
| `visual_planner.py` | Add visual direction, types, prompts, claims, beats and on-screen text |
| `scene_validator.py` | Validate contract, exact text coverage, source/claim state and warnings |
| `media_producer.py` | Create one Kokoro WAV per scene and acquire/render visual assets |
| `pixabay_media.py` | Pixabay-only stock adapter; no Pexels calls |
| `diagram_renderer.py` | Original local diagrams, text compositions and data charts |
| `assemble_v2.py` | FFmpeg assembly driven by actual WAV durations |
| `qc_scene_sync.py` | Verify audio, visuals, timeline and final MP4 |

## Provider and rights policy

- `stock` resolves through Pixabay only in this release.
- `rendered` creates original local visuals.
- `generated` is deliberately rejected until an actual provider is approved and integrated.
- `manual` and `screencast` require operator-supplied media.
- Pixabay items are marked `review_required`; metadata is preserved for final human rights review.
- Music and sound effects are not downloaded automatically. An LLM suggestion is not proof of a license.
- The configured Pexels key is ignored by the new pipeline.

## Timing

Target duration is 3–25 seconds per scene. Less than 2 seconds and more than 30 seconds trigger warnings; they are not automatic hard failures. Actual scene time comes from measured WAV duration.

## Risks and mitigations

- LLM may alter wording: exact contiguous excerpt checks block the next stage.
- LLM may claim facts are verified: LLM output has no trusted verification field; Python sets `verify_before_publish` or `no_source`.
- API may not support JSON Schema response format: use JSON Object fallback and mandatory local Pydantic v2 validation.
- Stock API may rate-limit: retain errors in the manifest and use the internal renderer fallback for that scene.
- `speaker_emotion` is editorial metadata only; current Kokoro voice does not expose reliable emotion control.
- The initial renderer supports local static graphics; generated video and advanced motion design are later production stages.

## Rollout

Use `video-farm-semantic run` for the new route. Do not silently route the legacy `video-farm run` command into the new pipeline until the new Windows E2E is reviewed and accepted.
