from pathlib import Path

import pytest

from course_policy.ai_config import load_ai_config


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "openai.local.toml"
    path.write_text(text, encoding="utf-8")
    return path


BASE_CONFIG = """
[openai]
api_key_env = "OPENAI_API_KEY"
model = "SET_MODEL_IN_LOCAL_CONFIG"
timeout_seconds = 60
max_retries = 2

[workflow]
mode = "dry_run"
max_requests_per_run = 0
monthly_budget_usd = 0.0
log_dir = "../data_policy_pipeline/logs/ai"
raw_response_dir = "../data_policy_pipeline/logs/ai/raw_responses"
parsed_response_dir = "../data_policy_pipeline/logs/ai/parsed_responses"

[prompts]
discovery_prompt_version = "catalog_discovery_v0"
classification_prompt_version = "policy_classification_v0"
schema_version = "course_policy_ai_v0"
"""


def test_dry_run_config_does_not_require_api_key(tmp_path):
    path = write_config(tmp_path, BASE_CONFIG)

    config = load_ai_config(path, root=tmp_path, environ={})

    assert config.workflow.mode == "dry_run"
    assert config.api_key_present is False
    assert config.live_enabled is False


def test_live_config_requires_api_key(tmp_path):
    path = write_config(
        tmp_path,
        BASE_CONFIG.replace('mode = "dry_run"', 'mode = "live"')
        .replace('model = "SET_MODEL_IN_LOCAL_CONFIG"', 'model = "reviewed-model-id"')
        .replace("max_requests_per_run = 0", "max_requests_per_run = 5")
        .replace("monthly_budget_usd = 0.0", "monthly_budget_usd = 10.0"),
    )

    with pytest.raises(ValueError, match=r"OPENAI_API_KEY"):
        load_ai_config(path, root=tmp_path, environ={})


def test_live_config_rejects_placeholder_model(tmp_path):
    path = write_config(
        tmp_path,
        BASE_CONFIG.replace('mode = "dry_run"', 'mode = "live"')
        .replace("max_requests_per_run = 0", "max_requests_per_run = 5")
        .replace("monthly_budget_usd = 0.0", "monthly_budget_usd = 10.0"),
    )

    with pytest.raises(ValueError, match="explicit OpenAI model id"):
        load_ai_config(path, root=tmp_path, environ={"OPENAI_API_KEY": "present"})


def test_live_config_passes_with_key_budget_and_explicit_model(tmp_path):
    path = write_config(
        tmp_path,
        BASE_CONFIG.replace('mode = "dry_run"', 'mode = "live"')
        .replace('model = "SET_MODEL_IN_LOCAL_CONFIG"', 'model = "reviewed-model-id"')
        .replace("max_requests_per_run = 0", "max_requests_per_run = 5")
        .replace("monthly_budget_usd = 0.0", "monthly_budget_usd = 10.0"),
    )

    config = load_ai_config(path, root=tmp_path, environ={"OPENAI_API_KEY": "present"})

    assert config.live_enabled is True
    assert config.api_key_present is True
    assert config.workflow.max_requests_per_run == 5
