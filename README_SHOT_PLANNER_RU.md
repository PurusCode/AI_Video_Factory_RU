# AI Video Factory RU — Engine 2.0 / Shot Planner, этап 1

## Что добавлено

Новый `src/video_farm/director_shots.py` превращает утверждённые режиссёрские beats в монтажные планы shot-level.

- Один исходный beat превращается в 1–4 самостоятельных shot, только если есть смысловая смена действия, объекта, масштаба или визуального аргумента.
- В каждом shot сохраняются `source_beat_id` и точный `spoken_text`.
- Python проверяет речь внутри каждого исходного beat: пропуски, перестановки, дубли и перефразирование блокируют производство.
- Shot ID нумеруются последовательно (`b01_s01`, `b01_s02`).
- План сохраняется в `shot_plan.json`; прогресс — в `shot_plan.progress.json`, откуда можно продолжить прерванное планирование.
- Модель не задаёт таймкоды и длительности. Каждый shot озвучивается Kokoro, длительность берётся из измеренного WAV.

## Установка в локальную копию

1. Распакуйте ZIP в корень репозитория `video-farm`, сохранив структуру папок.
2. В PowerShell из корня репозитория выполните проверку патча:

```powershell
git apply --check .\PATCH_PRODUCTION_DIRECTOR.diff
```

3. Только если проверка прошла без ошибок, примените патч:

```powershell
git apply .\PATCH_PRODUCTION_DIRECTOR.diff
```

Патч меняет только `src/video_farm/production_director.py`: импортирует shot planner и передаёт его результат в существующую стадию Kokoro/монтажа. Старый production pipeline, `.env`, `data/`, `output/` и зависимости не затрагиваются.

## Проверки

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_director_shots.py -q
.\.venv\Scripts\python.exe -X utf8 -m pytest tests -q
```

После проверок пилот запускается в новом каталоге (не поверх прежних результатов):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m video_farm.production_director `
  --storyboard ".\output\semantic_runs\semantic-e2e-2026-11-07\storyboard_draft.json" `
  --out ".\output\semantic_runs\engine2-shot-pilot-10-v1" `
  --scene-limit 10 --batch-size 2 --speed 0.9 --revision-rounds 2
```

## Важное ограничение этапа 1

Это первый слой Shot Planner / EDL, а не весь Engine 2.0. Визуалы пока поставляются прежними адаптерами Pixabay и локальной графикой. Следующие этапы — ранжирование нескольких stock-кандидатов, анимированный motion-graphics renderer, новый монтажный механизм и критика фактически закодированных кадров.

Ещё один нюанс: на этом этапе каждый shot получает отдельный Kokoro WAV. Поэтому после пилота важно оценить естественность стыков речи. Если короткие фразы звучат искусственно, следующий этап должен сохранить непрерывную озвучку исходного beat и привязывать смены видеопланов к точным временным anchors внутри общего WAV (forced alignment или аккуратное выравнивание), а не дробить сам голос.
