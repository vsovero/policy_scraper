"""Auditable OpenAI API smoke-test utilities.

The project keeps live calls explicit and logged. This module does not perform
catalog discovery or policy classification; it verifies that configured API
access can make a tiny Responses API request when workflow mode is live.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ai_config import AIConfig, load_ai_config


SMOKE_TASK_TYPE = "api_smoke"
SMOKE_INPUT = "Return exactly this text and nothing else: API_OK"


@dataclass(frozen=True)
class AISmokeOutput:
    call_id: str
    task_type: str
    mode: str
    model: str
    validation_status: str
    output_text: str
    metadata_path: Path
    raw_response_path: Path | None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_api_smoke(config: AIConfig) -> AISmokeOutput:
    """Run or dry-run a tiny OpenAI Responses API connectivity check."""
    config.workflow.log_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.raw_response_dir.mkdir(parents=True, exist_ok=True)
    config.workflow.parsed_response_dir.mkdir(parents=True, exist_ok=True)

    call_id = f"{SMOKE_TASK_TYPE}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    created_at = utc_now()
    raw_response_path: Path | None = None
    output_text = ""
    validation_status = "dry_run"
    raw_response: dict[str, Any] | None = None
    error_type = ""
    error_message = ""

    if config.live_enabled:
        raw_response_path = config.workflow.raw_response_dir / f"{call_id}.json"
        try:
            response = _create_response(config)
            output_text = str(getattr(response, "output_text", "")).strip()
            validation_status = "passed" if output_text == "API_OK" else "unexpected_output"
            raw_response = _response_to_dict(response)
        except Exception as exc:  # pragma: no cover - exact SDK errors vary by version.
            validation_status = "api_error"
            error_type = type(exc).__name__
            error_message = _safe_error_message(str(exc))
            raw_response = {"error_type": error_type, "error_message": error_message}
        raw_response_path.write_text(json.dumps(raw_response, indent=2, sort_keys=True), encoding="utf-8")

    metadata = {
        "call_id": call_id,
        "task_type": SMOKE_TASK_TYPE,
        "mode": config.workflow.mode,
        "model": config.openai.model,
        "prompt_version": "api_smoke_v0",
        "schema_version": config.prompts.schema_version,
        "input_hash": sha256_text(SMOKE_INPUT),
        "output_hash": sha256_text(output_text) if output_text else "",
        "raw_response_path": str(raw_response_path) if raw_response_path else "",
        "validation_status": validation_status,
        "error_type": error_type,
        "error_message": error_message,
        "created_at": created_at,
        "notes": "Connectivity check only; not a catalog-discovery or policy-classification result.",
    }
    metadata_path = config.workflow.parsed_response_dir / f"{call_id}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    _append_jsonl(config.workflow.log_dir / "api_call_log.jsonl", metadata)

    return AISmokeOutput(
        call_id=call_id,
        task_type=SMOKE_TASK_TYPE,
        mode=config.workflow.mode,
        model=config.openai.model,
        validation_status=validation_status,
        output_text=output_text,
        metadata_path=metadata_path,
        raw_response_path=raw_response_path,
    )


def _create_response(config: AIConfig) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on local environment.
        raise RuntimeError("The openai package is required for live API calls. Install project dependencies.") from exc

    client = OpenAI(
        api_key=os.environ[config.openai.api_key_env],
        timeout=config.openai.timeout_seconds,
        max_retries=config.openai.max_retries,
    )
    return client.responses.create(model=config.openai.model, input=SMOKE_INPUT)


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "dict"):
        return response.dict()
    return {"repr": repr(response), "output_text": str(getattr(response, "output_text", ""))}


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _safe_error_message(message: str) -> str:
    exact_key = os.environ.get("OPENAI_API_KEY", "")
    if exact_key:
        message = message.replace(exact_key, "[redacted]")
    return re.sub(r"sk-[A-Za-z0-9*_-]+", "[redacted-api-key]", message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an auditable OpenAI API smoke test.")
    parser.add_argument("--config", type=Path, default=None, help="Path to local TOML config.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root. Defaults to auto-detection.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_ai_config(args.config, root=args.root)
    output = run_api_smoke(config)
    print(f"call_id: {output.call_id}")
    print(f"mode: {output.mode}")
    print(f"model: {output.model}")
    print(f"validation_status: {output.validation_status}")
    print(f"metadata_path: {output.metadata_path}")
    if output.raw_response_path:
        print(f"raw_response_path: {output.raw_response_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
