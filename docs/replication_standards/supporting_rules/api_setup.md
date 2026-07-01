# API Setup and Workflow

Authority: BINDING STAGE RULE. This file governs API configuration, live/off
modes, and API audit metadata. It does not make live API calls part of the
required journal rebuild path.

This project uses OpenAI API calls only in controlled, auditable stages. API access should be configured before any code path is allowed to make live requests.

## Local Secret Setup

Create a local config file from the committed template:

```bash
cd policy_scraper
cp config/openai.example.toml config/openai.local.toml
```

Then edit `config/openai.local.toml`:

- keep `api_key_env = "OPENAI_API_KEY"` unless you intentionally use a different environment variable;
- set `model` to the reviewed model id for the pilot run;
- leave `mode = "dry_run"` until the dry-run logs look correct;
- set a positive `max_requests_per_run` and `monthly_budget_usd` before switching to `mode = "live"`.

Set the API key in the shell or local environment manager, never in a committed file:

```bash
export OPENAI_API_KEY="..."
```

`config/openai.local.toml`, `.env`, and `.env.*` are ignored by git.

## Validate Configuration

Run:

```bash
PYTHONPATH=src python -m course_policy.ai_config --config config/openai.local.toml --check
```

The check prints a redacted summary. It reports only whether the configured API-key environment variable is present; it never prints the key value.

Live mode validation fails unless all of these are true:

- the configured API-key environment variable is set;
- `model` is not a placeholder;
- `max_requests_per_run` is greater than zero;
- `monthly_budget_usd` is greater than zero.

## Workflow Modes

`off` disables AI workflow preparation.

`dry_run` is the default for pilot development. It can build prompt payloads and logs later, but must not call the API.

`live` is reserved for explicit runs after deterministic discovery/extraction steps have been attempted and the run budget is set.

## API Smoke Test

The Phase 3 pilot can run an API smoke-test workflow:

```bash
PYTHONPATH=src python -m course_policy.catalog_pilot --api-smoke --config config/openai.local.toml
```

In `dry_run` mode, this writes API metadata only and does not call OpenAI.

In `live` mode, it makes one tiny Responses API request and validates that the model returns `API_OK`. This confirms connectivity without creating source evidence or policy classifications.

## Audit Expectations

Every future live API call should write metadata under `artifacts/policy_data_internal/logs/ai`, including:

- task type;
- institution and target year identifiers;
- prompt version and schema version;
- model;
- input and output hashes;
- raw and parsed response paths;
- validation status;
- timestamp.

No API response should be treated as final policy data until it passes deterministic validation and remains traceable to saved source evidence.
