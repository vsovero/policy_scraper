import json
from pathlib import Path

import pandas as pd
import pytest

from course_policy.ai_config import AIConfig, AIWorkflowSettings, OpenAISettings, PromptSettings
from course_policy.catalog_api_comparison import (
    clean_snippet,
    extract_json_object,
    infer_years,
    run_catalog_api_comparison,
    select_sample,
)


def test_extract_json_object_handles_fenced_response():
    parsed = extract_json_object('```json\n{"likely_catalog_source": true}\n```')

    assert parsed["likely_catalog_source"] is True


def test_clean_snippet_removes_html_noise():
    assert clean_snippet("<title>X</title><script>bad()</script><p>Hello&nbsp;world</p>") == "X Hello world"


def test_infer_years_filters_and_sorts_catalog_years():
    assert infer_years("catalog 1988 2004-2006 2035 2020") == [2004, 2006, 2020]


def test_comparison_refuses_to_exceed_request_cap(monkeypatch, tmp_path):
    inventory_path = tmp_path / "data_policy_pipeline" / "interim"
    inventory_path.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "candidate_url": "https://example.edu/catalog.pdf",
                "needs_human_review": True,
                "pilot_rank": 1,
                "unitid": 1,
                "target_year": 2004,
                "source_id": "pilot-1",
                "institution_name": "Example U",
            }
        ]
    ).to_csv(inventory_path / "catalog_inventory_pilot.csv", index=False)

    monkeypatch.setattr(
        "course_policy.catalog_api_comparison.load_ai_config",
        lambda config_path, root: fake_config(tmp_path),
    )

    with pytest.raises(ValueError, match="max_requests_per_run"):
        run_catalog_api_comparison(tmp_path / "policy_pipeline", sample_size=2)


def test_select_sample_can_target_source_ids():
    inventory = pd.DataFrame(
        [
            {"source_id": "pilot-1", "candidate_url": "https://example.edu/a.pdf"},
            {"source_id": "pilot-2", "candidate_url": "https://example.edu/b.pdf"},
        ]
    )

    selected = select_sample(inventory, sample_size=1, source_ids=["pilot-2"])

    assert selected["source_id"].tolist() == ["pilot-2"]


def fake_config(tmp_path: Path):
    return AIConfig(
        path=tmp_path / "openai.local.toml",
        openai=OpenAISettings(
            api_key_env="OPENAI_API_KEY",
            model="reviewed-model-id",
            timeout_seconds=60,
            max_retries=2,
        ),
        workflow=AIWorkflowSettings(
            mode="live",
            max_requests_per_run=1,
            monthly_budget_usd=1.0,
            log_dir=tmp_path / "data_policy_pipeline" / "logs" / "ai",
            raw_response_dir=tmp_path / "data_policy_pipeline" / "logs" / "ai" / "raw_responses",
            parsed_response_dir=tmp_path / "data_policy_pipeline" / "logs" / "ai" / "parsed_responses",
        ),
        prompts=PromptSettings(
            discovery_prompt_version="catalog_discovery_v0",
            classification_prompt_version="policy_classification_v0",
            schema_version="course_policy_ai_v0",
        ),
        api_key_present=True,
    )
