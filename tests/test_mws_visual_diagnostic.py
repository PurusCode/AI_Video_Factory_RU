from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "diagnose_visual_planner.py"
SPEC = importlib.util.spec_from_file_location("diagnose_visual_planner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_visual_prompt_contains_only_original_scene_fields():
    scenes = [{
        "id": "s_001",
        "block_id": "hook",
        "voice_text": "Фрагмент речи",
        "meaning": "Смысл сцены",
        "purpose": "Цель сцены",
        "visual_type": "chart",  # must not be sent back to the model
        "chart_data": {"values": [1, 2]},
    }]
    prompt = MODULE.build_visual_prompt(scenes)
    assert '"scene_id": "s_001"' in prompt
    assert '"voice_text": "Фрагмент речи"' in prompt
    assert "chart_data" not in prompt
    assert '"visual_type": "chart"' not in prompt


def test_error_classification_distinguishes_timeout_and_schema_unsupported():
    class APITimeoutError(Exception):
        pass

    class UnsupportedParameter(Exception):
        pass

    assert MODULE.classify_error(APITimeoutError("Request timed out")) == "timeout"
    assert MODULE.classify_error(UnsupportedParameter("response_format unsupported")) == "format_unsupported"
    assert MODULE.classify_error(ValueError("unexpected response")) == "api_error"


def test_provider_host_does_not_preserve_api_path():
    assert MODULE.provider_host("https://gpt.example.test/projects/private/openai/v1") == "gpt.example.test"


def test_tiny_schema_probe_has_closed_object_contract():
    assert MODULE.TINY_SCHEMA["additionalProperties"] is False
    assert set(MODULE.TINY_SCHEMA["required"]) == set(MODULE.TINY_SCHEMA["properties"])


def test_request_builder_strict_mode_uses_full_visual_schema():
    from types import SimpleNamespace

    _, kwargs = MODULE.build_visual_request(
        SimpleNamespace(model="mws-test"), "prompt", "json_schema_strict", 5000
    )
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert kwargs["temperature"] == 0.35
    assert kwargs["max_tokens"] == 5000


def test_request_builder_json_object_mode_does_not_send_strict_schema():
    from types import SimpleNamespace

    _, kwargs = MODULE.build_visual_request(
        SimpleNamespace(model="mws-test"), "prompt", "json_object", 5000
    )
    assert kwargs["response_format"] == {"type": "json_object"}


def test_request_builder_prompt_only_omits_response_format():
    from types import SimpleNamespace

    messages, kwargs = MODULE.build_visual_request(
        SimpleNamespace(model="mws-test"), "prompt", "prompt_only", 5000
    )
    assert "response_format" not in kwargs
    assert "корректный JSON" in messages[0]["content"]


def test_timeout_report_keeps_requested_format_instead_of_null(monkeypatch):
    from types import SimpleNamespace

    provider = SimpleNamespace(name="primary", model="mws-test", api_key="secret")

    def timeout(*args, **kwargs):
        raise TimeoutError("Request timed out")

    monkeypatch.setattr(MODULE, "request_visual_plan", timeout)
    result = MODULE.run_visual_probe(
        provider,
        [{"id": "s_001", "block_id": "hook", "voice_text": "text", "meaning": "meaning", "purpose": "purpose"}],
        30.0,
        response_mode="json_schema_strict",
    )
    assert result["status"] == "timeout"
    assert result["requested_response_mode"] == "json_schema_strict"
    assert result["response_format"] == "json_schema_strict"


def test_clone_ollama_provider_uses_existing_secondary_endpoint_without_mutating_it():
    from dataclasses import dataclass

    @dataclass
    class Provider:
        name: str
        base_url: str
        api_key: str
        model: str

    original = Provider(
        name="secondary", base_url="http://localhost:11434/v1",
        api_key="local-token", model="qwen2.5:14b-instruct",
    )
    key, candidate = MODULE.clone_ollama_provider(
        original, "frob/qwen3.5-instruct:27b"
    )
    assert key == "ollama_frob_qwen3_5_instruct_27b"
    assert candidate.model == "frob/qwen3.5-instruct:27b"
    assert candidate.base_url == original.base_url
    assert candidate.api_key == original.api_key
    assert original.model == "qwen2.5:14b-instruct"
    assert original.name == "secondary"


def test_local_ollama_requests_get_explicit_bounded_context():
    from types import SimpleNamespace

    provider = SimpleNamespace(base_url="http://localhost:11434/v1")
    assert MODULE.ollama_request_options(provider, 8192) == {
        "extra_body": {"options": {"num_ctx": 8192}}
    }


def test_remote_provider_does_not_receive_ollama_options():
    from types import SimpleNamespace

    provider = SimpleNamespace(base_url="https://api.example.test/v1")
    assert MODULE.ollama_request_options(provider, 8192) == {}
