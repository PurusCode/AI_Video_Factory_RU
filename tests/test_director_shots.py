import json

import pytest
from pydantic import ValidationError

from video_farm import director_shots
from video_farm.director_shots import Shot, _check_group_coverage, plan_shots


def shot(shot_id, source_beat_id, spoken_text):
    return {"shot_id": shot_id, "source_beat_id": source_beat_id,
            "spoken_text": spoken_text}


def test_shot_coverage_allows_meaningful_subdivision():
    _check_group_coverage(
        [{"spoken_text": "Сначала запрос. Затем ответ."}],
        [shot("b01_s01", "b01", "Сначала запрос."),
         shot("b01_s02", "b01", "Затем ответ.")],
        "s_001",
    )


def test_shot_coverage_accepts_one_shot_for_a_whole_beat():
    _check_group_coverage(
        [{"spoken_text": "Один кадр удерживает всю мысль."}],
        [shot("b01_s01", "b01", "Один кадр удерживает всю мысль.")],
        "s_001",
    )


def test_shot_coverage_rejects_missing_words():
    with pytest.raises(ValueError, match="exactly preserve"):
        _check_group_coverage(
            [{"spoken_text": "Сначала запрос. Затем ответ."}],
            [shot("b01_s01", "b01", "Сначала запрос.")],
            "s_001",
        )


def test_shot_coverage_rejects_reordered_fragments():
    with pytest.raises(ValueError, match="exactly preserve"):
        _check_group_coverage(
            [{"spoken_text": "Сначала запрос. Затем ответ."}],
            [shot("b01_s01", "b01", "Затем ответ."),
             shot("b01_s02", "b01", "Сначала запрос.")],
            "s_001",
        )


def test_shot_coverage_rejects_unknown_source_beat():
    with pytest.raises(ValueError, match="unknown source_beat_id"):
        _check_group_coverage(
            [{"spoken_text": "Фраза."}],
            [shot("b02_s01", "b02", "Фраза.")],
            "s_001",
        )


def test_shot_coverage_rejects_duplicate_shot_ids():
    with pytest.raises(ValueError, match="duplicate shot_id"):
        _check_group_coverage(
            [{"spoken_text": "Фраза один. Фраза два."}],
            [shot("b01_s01", "b01", "Фраза один."),
             shot("b01_s01", "b01", "Фраза два.")],
            "s_001",
        )


def test_shot_coverage_rejects_more_than_four_shots_per_beat():
    with pytest.raises(ValueError, match="more than four"):
        _check_group_coverage(
            [{"spoken_text": "А. Б. В. Г. Д."}],
            [shot(f"b01_s{i:02d}", "b01", text)
             for i, text in enumerate(["А.", "Б.", "В.", "Г.", "Д."], 1)],
            "s_001",
        )


# Additional regression coverage for the complete shot-planning path.
def _director_beat(text: str) -> dict:
    return {
        "spoken_text": text,
        "visual_type": "illustration",
        "visual_description": "Визуальная метафора смыслового фрагмента",
        "asset_strategy": "rendered",
        "provider_id": "internal_renderer",
        "gen_prompt": None,
        "search_queries": [],
        "on_screen_text": [],
        "motion": "slow_zoom",
        "transition_in": "cut",
        "audio_sfx": [],
    }


def _director_shot(text: str, number: int, source_id: str = "b01") -> dict:
    return {
        **_director_beat(text),
        "shot_id": f"{source_id}_s{number:02d}",
        "source_beat_id": source_id,
        "cut_reason": "Смена визуального аргумента",
    }


def _shot_plan_inputs():
    scenes = [{"id": "s_001", "meaning": "Обработка запроса", "purpose": "Показать ход рассуждения"}]
    plans = [{
        "scene_id": "s_001",
        "editorial_intent": "Показать последовательность формирования ответа",
        "claims": [],
        "music_cue": "",
        "beats": [
            _director_beat("Модель формирует ответ. Затем проверяет контекст."),
            _director_beat("И выбирает продолжение."),
        ],
    }]
    rows = [
        _director_shot("И выбирает продолжение.", 1, "b02"),
        _director_shot("Затем проверяет контекст.", 2, "b01"),
        _director_shot("Модель формирует ответ.", 1, "b01"),
    ]
    return scenes, plans, rows


def _install_shot_router(monkeypatch, callback):
    class FakeRouter:
        def __init__(self, _settings):
            pass

        def complete(self, schema, _system, prompt, **_kwargs):
            return callback(schema, prompt)

    monkeypatch.setattr(director_shots, "StructuredLLMRouter", FakeRouter)


def test_shot_coverage_rejects_nonsequential_shot_ids():
    source = [{"spoken_text": "Первая часть. Вторая часть."}]
    rows = [_director_shot("Первая часть.", 1), _director_shot("Вторая часть.", 3)]

    with pytest.raises(ValueError, match="expected b01_s02"):
        _check_group_coverage(source, rows, "s_001")


def test_shot_schema_rejects_provider_strategy_mismatch():
    row = _director_shot("Пользователь печатает запрос.", 1)
    row.update({
        "asset_strategy": "stock",
        "provider_id": "internal_renderer",
        "visual_type": "video",
        "search_queries": ["person typing on laptop"],
    })

    with pytest.raises(ValidationError):
        Shot.model_validate(row)


def test_shot_schema_rejects_model_generated_timestamps():
    row = _director_shot("Исходная фраза.", 1)
    row["start_sec"] = 1.25

    with pytest.raises(ValidationError):
        Shot.model_validate(row)


def test_plan_shots_validates_sorts_and_persists_shot_edl(tmp_path, monkeypatch):
    scenes, plans, rows = _shot_plan_inputs()

    def respond(schema, prompt):
        request = json.loads(prompt.split("\n", 1)[1])
        assert request[0]["source_beats"][0]["source_beat_id"] == "b01"
        return schema.model_validate({"scenes": [{"scene_id": "s_001", "shots": rows}]})

    _install_shot_router(monkeypatch, respond)
    output = tmp_path / "shot_plan.json"
    result = plan_shots(object(), scenes, plans, output)

    assert result["status"] == "validated"
    assert result["source_beat_count"] == 2
    assert result["shot_count"] == 3
    assert [row["shot_id"] for row in result["plans"][0]["beats"]] == [
        "b01_s01", "b01_s02", "b02_s01"
    ]
    assert json.loads(output.read_text(encoding="utf-8")) == result
    checkpoint = json.loads(output.with_suffix(".progress.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "complete"
    assert checkpoint["completed_scene_count"] == 1


def test_plan_shots_reuses_completed_checkpoint_without_llm_call(tmp_path, monkeypatch):
    scenes, plans, rows = _shot_plan_inputs()

    def respond(schema, _prompt):
        return schema.model_validate({"scenes": [{"scene_id": "s_001", "shots": rows}]})

    _install_shot_router(monkeypatch, respond)
    output = tmp_path / "shot_plan.json"
    first = plan_shots(object(), scenes, plans, output)

    class NoCallRouter:
        def __init__(self, _settings):
            pass

        def complete(self, *_args, **_kwargs):
            pytest.fail("Completed checkpoint should not call the LLM")

    monkeypatch.setattr(director_shots, "StructuredLLMRouter", NoCallRouter)
    second = plan_shots(object(), scenes, plans, output)
    assert second == first


def test_plan_shots_rejects_checkpoint_for_changed_input(tmp_path, monkeypatch):
    scenes, plans, rows = _shot_plan_inputs()

    def respond(schema, _prompt):
        return schema.model_validate({"scenes": [{"scene_id": "s_001", "shots": rows}]})

    _install_shot_router(monkeypatch, respond)
    output = tmp_path / "shot_plan.json"
    plan_shots(object(), scenes, plans, output)
    changed_scenes = [{**scenes[0], "meaning": "Другое содержание"}]

    with pytest.raises(ValueError, match="different input"):
        plan_shots(object(), changed_scenes, plans, output)


def test_plan_shots_rejects_wrong_scene_ids_from_model(tmp_path, monkeypatch):
    scenes, plans, rows = _shot_plan_inputs()

    def respond(schema, _prompt):
        return schema.model_validate({"scenes": [{"scene_id": "s_999", "shots": rows}]})

    _install_shot_router(monkeypatch, respond)
    with pytest.raises(ValueError, match="wrong scene IDs"):
        plan_shots(object(), scenes, plans, tmp_path / "shot_plan.json")
