"""Regression tests for Engine 2.4 editorial prompt policy."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _constant(relative_path: str, name: str) -> str:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = ast.literal_eval(node.value)
                assert isinstance(value, str), f"{name} must be a string constant"
                return value
    raise AssertionError(f"Prompt constant not found: {relative_path}:{name}")


def test_director_prompt_rejects_fabricated_interfaces_and_details() -> None:
    prompt = _constant("src/video_farm/production_director.py", "DIRECTOR_SYSTEM")
    assert "EDITORIAL_POLICY_ENGINE_2_4" in prompt
    assert "Не создавай псевдоскриншоты" in prompt
    assert "Не выдумывай названия авторов" in prompt
    assert "одним beat" in prompt
    assert "Стоковый кадр — иллюстрация" in prompt


def test_critic_prompt_checks_factual_visual_integrity() -> None:
    prompt = _constant("src/video_farm/production_director.py", "CRITIC_SYSTEM")
    assert "EDITORIAL_REVIEW_ENGINE_2_4" in prompt
    assert "Блокируй реалистичный псевдоинтерфейс" in prompt
    assert "нейтральной иллюстрацией контекста" in prompt


def test_repair_prompt_preserves_one_thought_per_beat() -> None:
    prompt = _constant("src/video_farm/production_director.py", "REPAIR_SYSTEM")
    assert "EDITORIAL_REPAIR_ENGINE_2_4" in prompt
    assert "Не создавай фиктивные интерфейсы" in prompt
    assert "Не дроби речь ради разнообразия" in prompt


def test_shot_planner_defaults_to_one_shot_per_source_beat() -> None:
    prompt = _constant("src/video_farm/director_shots.py", "SYSTEM_PROMPT")
    assert "SHOT_POLICY_ENGINE_2_4" in prompt
    assert "ровно один shot на каждый source beat" in prompt
    assert "для разнообразия" in prompt
    assert "cut_reason должен называть конкретную смену" in prompt


def test_shot_planner_forbids_invented_interfaces_and_factual_details() -> None:
    prompt = _constant("src/video_farm/director_shots.py", "SYSTEM_PROMPT")
    assert "Не придумывай псевдоинтерфейсы" in prompt
    assert "Не используй случайный сток как доказательство" in prompt
