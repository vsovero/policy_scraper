"""Score whether Phase 3 reproduces legacy URLs before expanding beyond them."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

import pandas as pd

from .ai_config import repo_root_from_cwd
from .catalog_retrieval import retrieve_url


DATA_DIR = Path("artifacts/policy_data_internal")
INTERIM_DIR = DATA_DIR / "interim"
REVIEW_DIR = DATA_DIR / "review"
LOG_DIR = DATA_DIR / "logs"

RETRIEVED_STATUSES = {"retrieved", "retrieved_truncated"}


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def suffixed_path(path: Path, suffix: str) -> Path:
    if not suffix:
        return path
    clean_suffix = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in suffix.strip())
    return path.with_name(f"{path.stem}_{clean_suffix}{path.suffix}")


def normalized_url(url: object) -> str:
    text = clean_text(url)
    if not text:
        return ""
    parsed = urlparse(text)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = unquote(parsed.path).rstrip("/")
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def score_legacy_reproduction(
    legacy: pd.DataFrame,
    comparison: pd.DataFrame,
    *,
    timeout_seconds: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    legacy = legacy.loc[legacy["legacy_url"].fillna("").astype(str).str.strip().ne("")].copy()
    for _, legacy_row in legacy.sort_values(["institution_name", "target_year", "legacy_url"]).iterrows():
        legacy_url = clean_text(legacy_row["legacy_url"])
        result = retrieve_url(legacy_url, timeout_seconds=timeout_seconds, max_bytes=2_000_000)
        unitid = int(legacy_row["unitid"])
        target_year = int(legacy_row["target_year"])
        matched = comparison.loc[
            comparison["unitid"].astype(int).eq(unitid) & comparison["start_year"].astype(int).eq(target_year)
        ]
        pipeline_url = ""
        best_url = ""
        post_ai_url = ""
        legacy_url_in_panel = ""
        if not matched.empty:
            row = matched.iloc[0]
            best_url = clean_text(row.get("best_url", ""))
            post_ai_url = clean_text(row.get("post_ai_best_url", ""))
            pipeline_url = post_ai_url or best_url
            legacy_url_in_panel = clean_text(row.get("legacy_url", ""))
        active = clean_text(result.get("retrieval_status", "")) in RETRIEVED_STATUSES
        exact = normalized_url(pipeline_url) == normalized_url(legacy_url)
        redirect_exact = bool(clean_text(result.get("final_url", ""))) and normalized_url(pipeline_url) == normalized_url(
            result.get("final_url", "")
        )
        panel_preserved = normalized_url(legacy_url_in_panel) == normalized_url(legacy_url)
        rows.append(
            {
                "unitid": unitid,
                "institution_name": clean_text(legacy_row["institution_name"]),
                "target_year": target_year,
                "legacy_url": legacy_url,
                "legacy_retrieval_status": clean_text(result.get("retrieval_status", "")),
                "legacy_http_status": clean_text(result.get("http_status", "")),
                "legacy_final_url": clean_text(result.get("final_url", "")),
                "legacy_content_type": clean_text(result.get("content_type", "")),
                "legacy_active": active,
                "pipeline_final_url": pipeline_url,
                "pipeline_best_url": best_url,
                "pipeline_post_ai_best_url": post_ai_url,
                "legacy_url_preserved_in_panel": panel_preserved,
                "active_legacy_exact_or_redirect_reproduced": active and (exact or redirect_exact),
                "active_legacy_year_has_pipeline_url": active and bool(pipeline_url),
                "active_legacy_not_exact_but_year_found": active and bool(pipeline_url) and not (exact or redirect_exact),
                "active_legacy_missing_pipeline_url": active and not bool(pipeline_url),
            }
        )
    return pd.DataFrame(rows)


def read_final_panel(repo_root: Path, *, suffix: str, comparison_suffix: str) -> pd.DataFrame:
    mockup_csv = suffixed_path(repo_root / REVIEW_DIR / "catalog_url_spotcheck_mockup.csv", suffix)
    mockup_xlsx = suffixed_path(repo_root / REVIEW_DIR / "catalog_url_spotcheck_mockup.xlsx", suffix)
    if mockup_csv.exists():
        panel = pd.read_csv(mockup_csv, low_memory=False)
    elif mockup_xlsx.exists():
        panel = pd.read_excel(mockup_xlsx, sheet_name="spotcheck_mockup")
    else:
        panel = pd.DataFrame()
    if panel.empty:
        return panel
    panel["post_ai_best_url"] = panel.get("best_url", "").map(clean_text)
    panel["post_ai_best_url_source"] = panel.get("best_url_source", "").map(clean_text)

    if not comparison_suffix:
        return panel
    comparison_path = suffixed_path(repo_root / REVIEW_DIR / "catalog_ai_root_year_coverage_comparison.csv", comparison_suffix)
    if not comparison_path.exists():
        return panel
    comparison = pd.read_csv(comparison_path, low_memory=False)
    if comparison.empty:
        return panel
    keep = ["unitid", "start_year", "post_ai_best_url", "post_ai_best_url_source"]
    comparison = comparison[[col for col in keep if col in comparison.columns]].copy()
    if not {"unitid", "start_year", "post_ai_best_url"}.issubset(comparison.columns):
        return panel
    comparison["unitid"] = comparison["unitid"].astype(int)
    comparison["start_year"] = comparison["start_year"].astype(int)
    comparison = comparison.drop_duplicates(["unitid", "start_year"], keep="first")
    panel["unitid"] = panel["unitid"].astype(int)
    panel["start_year"] = panel["start_year"].astype(int)
    panel = panel.merge(
        comparison,
        on=["unitid", "start_year"],
        how="left",
        suffixes=("", "_ai_overlay"),
    )
    overlay_url = panel["post_ai_best_url_ai_overlay"].map(clean_text)
    overlay_mask = overlay_url.ne("")
    panel.loc[overlay_mask, "post_ai_best_url"] = overlay_url[overlay_mask]
    if "post_ai_best_url_source_ai_overlay" in panel.columns:
        overlay_source = panel["post_ai_best_url_source_ai_overlay"].map(clean_text)
        panel.loc[overlay_mask, "post_ai_best_url_source"] = overlay_source[overlay_mask]
    return panel.drop(columns=[col for col in panel.columns if col.endswith("_ai_overlay")])


def between_legacy_gap_denominator(legacy: pd.DataFrame) -> tuple[int, int]:
    legacy = legacy.loc[legacy["legacy_url"].fillna("").astype(str).str.strip().ne("")].copy()
    if legacy.empty:
        return 0, 0
    institution_count = 0
    gap_year_count = 0
    for _, group in legacy.groupby("unitid"):
        years = sorted(set(group["target_year"].astype(int)))
        if len(years) < 2:
            continue
        institution_count += 1
        gap_year_count += max(0, max(years) - min(years) + 1 - len(years))
    return institution_count, gap_year_count


def write_summary(path: Path, suffix: str, scores: pd.DataFrame, legacy: pd.DataFrame) -> None:
    active = scores.loc[scores["legacy_active"]]
    inactive = scores.loc[~scores["legacy_active"]]
    active_count = len(active)
    exact_count = int(active["active_legacy_exact_or_redirect_reproduced"].sum()) if active_count else 0
    year_count = int(active["active_legacy_year_has_pipeline_url"].sum()) if active_count else 0
    not_exact_count = int(active["active_legacy_not_exact_but_year_found"].sum()) if active_count else 0
    missing_count = int(active["active_legacy_missing_pipeline_url"].sum()) if active_count else 0
    gap_institutions, gap_years = between_legacy_gap_denominator(legacy)

    lines = [
        "# Legacy Reproduction Benchmark",
        "",
        f"Sample id: `{suffix}`",
        "",
        "## Active Legacy URL Reproduction",
        "",
        f"- Legacy URL rows tested: {len(scores)}",
        f"- Active legacy URLs: {active_count}",
        f"- Active legacy URLs exactly/equivalently reproduced: {exact_count} of {active_count}",
        f"- Active legacy URL years with any pipeline URL: {year_count} of {active_count}",
        f"- Active legacy URLs not exact but same target year found: {not_exact_count} of {active_count}",
        f"- Active legacy URLs missing any pipeline URL: {missing_count} of {active_count}",
        f"- Inactive/non-retrieved legacy URLs: {len(inactive)}",
        "",
        "## Between-Legacy Gap Fill",
        "",
        f"- Institutions with at least two legacy URL years: {gap_institutions}",
        f"- Between-legacy gap institution-years in this holdout: {gap_years}",
    ]
    if gap_years == 0:
        lines.append("- This holdout cannot estimate between-legacy gap filling because every institution has exactly one legacy URL year.")
    lines.extend(["", "## Inactive Legacy URL Statuses", ""])
    if inactive.empty:
        lines.append("- none")
    else:
        for status, count in inactive["legacy_retrieval_status"].value_counts().sort_index().items():
            lines.append(f"- {status}: {int(count)}")
    lines.extend(["", "## Active Legacy Reproduction Failures", ""])
    failures = active.loc[~active["active_legacy_exact_or_redirect_reproduced"]]
    if failures.empty:
        lines.append("- none")
    else:
        for _, row in failures.sort_values(["institution_name", "target_year"]).iterrows():
            pipeline = clean_text(row["pipeline_final_url"]) or "MISSING"
            lines.append(
                f"- {row['institution_name']} ({int(row['unitid'])}) AY {int(row['target_year'])}: "
                f"legacy={row['legacy_url']} | pipeline={pipeline}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    repo_root: Path,
    *,
    suffix: str,
    comparison_suffix: str,
    timeout_seconds: int = 8,
) -> tuple[Path, Path]:
    repo_root = repo_root.resolve()
    legacy_path = suffixed_path(repo_root / INTERIM_DIR / "catalog_batch4_legacy_leads.csv", suffix)
    legacy = pd.read_csv(legacy_path, low_memory=False)
    final_panel = read_final_panel(repo_root, suffix=suffix, comparison_suffix=comparison_suffix)
    scores = score_legacy_reproduction(legacy, final_panel, timeout_seconds=timeout_seconds)
    output_csv = suffixed_path(repo_root / REVIEW_DIR / "catalog_legacy_reproduction.csv", suffix)
    output_log = suffixed_path(repo_root / LOG_DIR / "catalog_legacy_reproduction.md", suffix)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(output_csv, index=False)
    write_summary(output_log, suffix, scores, legacy)
    return output_csv.resolve(), output_log.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--comparison-suffix", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=8)
    args = parser.parse_args(argv)
    repo_root = args.root.resolve() if args.root else repo_root_from_cwd()
    output_csv, output_log = run(
        repo_root,
        suffix=args.suffix,
        comparison_suffix=args.comparison_suffix,
        timeout_seconds=args.timeout_seconds,
    )
    print(f"legacy_reproduction_csv: {output_csv}")
    print(f"legacy_reproduction_log: {output_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
