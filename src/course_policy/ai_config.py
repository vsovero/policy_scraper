"""Configuration helpers for auditable OpenAI API workflow setup."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10.
    import tomli as tomllib


DEFAULT_CONFIG_PATH = Path("config/openai.local.toml")
EXAMPLE_CONFIG_PATH = Path("config/openai.example.toml")
ALLOWED_WORKFLOW_MODES = {"off", "dry_run", "live"}
PLACEHOLDER_MODELS = {"", "SET_MODEL_IN_LOCAL_CONFIG", "replace-with-model-id"}


@dataclass(frozen=True)
class OpenAISettings:
    api_key_env: str
    model: str
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True)
class AIWorkflowSettings:
    mode: str
    max_requests_per_run: int
    monthly_budget_usd: float
    log_dir: Path
    raw_response_dir: Path
    parsed_response_dir: Path


@dataclass(frozen=True)
class PromptSettings:
    discovery_prompt_version: str
    classification_prompt_version: str
    schema_version: str


@dataclass(frozen=True)
class AIConfig:
    path: Path
    openai: OpenAISettings
    workflow: AIWorkflowSettings
    prompts: PromptSettings
    api_key_present: bool

    @property
    def live_enabled(self) -> bool:
        return self.workflow.mode == "live"

    def redacted_summary(self) -> dict[str, object]:
        return {
            "config_path": str(self.path),
            "mode": self.workflow.mode,
            "model": self.openai.model,
            "api_key_env": self.openai.api_key_env,
            "api_key_present": self.api_key_present,
            "max_requests_per_run": self.workflow.max_requests_per_run,
            "monthly_budget_usd": self.workflow.monthly_budget_usd,
            "discovery_prompt_version": self.prompts.discovery_prompt_version,
            "classification_prompt_version": self.prompts.classification_prompt_version,
            "schema_version": self.prompts.schema_version,
        }


def repo_root_from_cwd(cwd: Path | None = None) -> Path:
    start = (cwd or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "course_policy").exists():
            return candidate
    return start


def default_config_path(root: Path) -> Path:
    local_path = root / DEFAULT_CONFIG_PATH
    if local_path.exists():
        return local_path
    return root / EXAMPLE_CONFIG_PATH


def load_ai_config(
    config_path: Path | str | None = None,
    *,
    root: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> AIConfig:
    repo_root = Path(root).resolve() if root is not None else repo_root_from_cwd()
    path = Path(config_path) if config_path is not None else default_config_path(repo_root)
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        raise FileNotFoundError(f"AI config file not found: {path}")

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    openai_data = data.get("openai", {})
    workflow_data = data.get("workflow", {})
    prompts_data = data.get("prompts", {})

    openai = OpenAISettings(
        api_key_env=str(openai_data.get("api_key_env", "OPENAI_API_KEY")),
        model=str(openai_data.get("model", "")),
        timeout_seconds=int(openai_data.get("timeout_seconds", 60)),
        max_retries=int(openai_data.get("max_retries", 2)),
    )
    workflow = AIWorkflowSettings(
        mode=str(workflow_data.get("mode", "off")).strip(),
        max_requests_per_run=int(workflow_data.get("max_requests_per_run", 0)),
        monthly_budget_usd=float(workflow_data.get("monthly_budget_usd", 0)),
        log_dir=_config_path(repo_root, workflow_data.get("log_dir", "../data_policy_pipeline/logs/ai")),
        raw_response_dir=_config_path(
            repo_root,
            workflow_data.get("raw_response_dir", "../data_policy_pipeline/logs/ai/raw_responses"),
        ),
        parsed_response_dir=_config_path(
            repo_root,
            workflow_data.get("parsed_response_dir", "../data_policy_pipeline/logs/ai/parsed_responses"),
        ),
    )
    prompts = PromptSettings(
        discovery_prompt_version=str(prompts_data.get("discovery_prompt_version", "")),
        classification_prompt_version=str(prompts_data.get("classification_prompt_version", "")),
        schema_version=str(prompts_data.get("schema_version", "")),
    )
    env = environ if environ is not None else os.environ
    config = AIConfig(
        path=path,
        openai=openai,
        workflow=workflow,
        prompts=prompts,
        api_key_present=bool(env.get(openai.api_key_env, "").strip()),
    )
    validate_ai_config(config)
    return config


def _config_path(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (root / path).resolve()


def validate_ai_config(config: AIConfig) -> None:
    errors: list[str] = []
    if config.workflow.mode not in ALLOWED_WORKFLOW_MODES:
        errors.append(
            f"workflow.mode must be one of {sorted(ALLOWED_WORKFLOW_MODES)}, got {config.workflow.mode!r}"
        )
    if config.openai.timeout_seconds <= 0:
        errors.append("openai.timeout_seconds must be positive")
    if config.openai.max_retries < 0:
        errors.append("openai.max_retries cannot be negative")
    if config.workflow.max_requests_per_run < 0:
        errors.append("workflow.max_requests_per_run cannot be negative")
    if config.workflow.monthly_budget_usd < 0:
        errors.append("workflow.monthly_budget_usd cannot be negative")
    if not config.prompts.discovery_prompt_version:
        errors.append("prompts.discovery_prompt_version is required")
    if not config.prompts.classification_prompt_version:
        errors.append("prompts.classification_prompt_version is required")
    if not config.prompts.schema_version:
        errors.append("prompts.schema_version is required")

    if config.workflow.mode == "live":
        if not config.api_key_present:
            errors.append(f"live mode requires ${config.openai.api_key_env} to be set")
        if config.openai.model.strip() in PLACEHOLDER_MODELS:
            errors.append("live mode requires an explicit OpenAI model id")
        if config.workflow.max_requests_per_run <= 0:
            errors.append("live mode requires workflow.max_requests_per_run > 0")
        if config.workflow.monthly_budget_usd <= 0:
            errors.append("live mode requires workflow.monthly_budget_usd > 0")

    if errors:
        raise ValueError("; ".join(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AI/OpenAI workflow configuration.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to TOML config. Defaults to config/openai.local.toml if present, otherwise example config.",
    )
    parser.add_argument("--root", type=Path, default=None, help="Repository root. Defaults to auto-detection.")
    parser.add_argument("--check", action="store_true", help="Print a redacted validation summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_ai_config(args.config, root=args.root)
    if args.check:
        for key, value in config.redacted_summary().items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
