from pathlib import Path
from types import SimpleNamespace

from course_policy.ai_client import run_api_smoke
from course_policy.ai_config import AIConfig, AIWorkflowSettings, OpenAISettings, PromptSettings


def test_api_smoke_dry_run_writes_metadata(tmp_path):
    config = fake_config(tmp_path, mode="dry_run")

    output = run_api_smoke(config)

    assert output.validation_status == "dry_run"
    assert output.raw_response_path is None
    assert output.metadata_path.exists()
    assert (tmp_path / "ai" / "api_call_log.jsonl").exists()


def test_api_smoke_live_uses_create_response_and_writes_raw(monkeypatch, tmp_path):
    config = fake_config(tmp_path, mode="live")

    def fake_create_response(_config):
        return SimpleNamespace(
            output_text="API_OK",
            model_dump=lambda mode: {"id": "resp_test", "output_text": "API_OK"},
        )

    monkeypatch.setattr("course_policy.ai_client._create_response", fake_create_response)

    output = run_api_smoke(config)

    assert output.validation_status == "passed"
    assert output.output_text == "API_OK"
    assert output.raw_response_path is not None
    assert output.raw_response_path.exists()


def test_api_smoke_live_logs_api_errors(monkeypatch, tmp_path):
    config = fake_config(tmp_path, mode="live")

    def fake_create_response(_config):
        raise RuntimeError("Incorrect API key provided: secret-value")

    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setattr("course_policy.ai_client._create_response", fake_create_response)

    output = run_api_smoke(config)

    assert output.validation_status == "api_error"
    assert output.raw_response_path is not None
    raw_text = output.raw_response_path.read_text(encoding="utf-8")
    assert "secret-value" not in raw_text
    assert "[redacted]" in raw_text


def test_api_smoke_live_redacts_masked_key_suffix(monkeypatch, tmp_path):
    config = fake_config(tmp_path, mode="live")

    def fake_create_response(_config):
        raise RuntimeError("Incorrect API key provided: sk-proj-********suffix")

    monkeypatch.setattr("course_policy.ai_client._create_response", fake_create_response)

    output = run_api_smoke(config)

    raw_text = output.raw_response_path.read_text(encoding="utf-8")
    assert "sk-proj" not in raw_text
    assert "suffix" not in raw_text
    assert "[redacted-api-key]" in raw_text


def fake_config(tmp_path: Path, *, mode: str):
    return AIConfig(
        path=tmp_path / "openai.local.toml",
        openai=OpenAISettings(
            api_key_env="OPENAI_API_KEY",
            model="reviewed-model-id",
            timeout_seconds=60,
            max_retries=2,
        ),
        workflow=AIWorkflowSettings(
            mode=mode,
            max_requests_per_run=1 if mode == "live" else 0,
            monthly_budget_usd=1.0 if mode == "live" else 0.0,
            log_dir=tmp_path / "ai",
            raw_response_dir=tmp_path / "ai" / "raw",
            parsed_response_dir=tmp_path / "ai" / "parsed",
        ),
        prompts=PromptSettings(
            discovery_prompt_version="catalog_discovery_v0",
            classification_prompt_version="policy_classification_v0",
            schema_version="course_policy_ai_v0",
        ),
        api_key_present=True,
    )
