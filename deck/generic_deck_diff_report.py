from __future__ import annotations

from html import escape
from typing import Any


def build_rich_deck_diff_report(
    archetype: str,
    baseline_result: dict[str, Any],
    tuned_result: dict[str, Any],
    retest_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retest = retest_results or {}
    package_comparison = build_package_comparison(
        baseline_result.get("package_counts", {}),
        tuned_result.get("package_counts", {}),
    )
    card_delta = build_card_delta(baseline_result.get("deck_names", []), tuned_result.get("deck_names", []))
    risk_flags = collect_risk_flags(retest)
    report = {
        "archetype": archetype,
        "score_summary": {
            "baseline_score": baseline_result.get("score", 0),
            "tuned_score": tuned_result.get("score", 0),
            "score_delta": round(float(tuned_result.get("score", 0) or 0) - float(baseline_result.get("score", 0) or 0), 4),
            "baseline_confidence": baseline_result.get("confidence", 0),
            "tuned_confidence": tuned_result.get("confidence", 0),
            "confidence_delta": round(float(tuned_result.get("confidence", 0) or 0) - float(baseline_result.get("confidence", 0) or 0), 4),
        },
        "baseline_deck_sections": baseline_result.get("deck_sections", {}),
        "tuned_deck_sections": tuned_result.get("deck_sections", {}),
        "repair_actions": {
            "baseline": baseline_result.get("repair_actions", []),
            "tuned": tuned_result.get("repair_actions", []),
        },
        "package_count_comparison": package_comparison,
        "cards_added": card_delta["cards_added"],
        "cards_removed": card_delta["cards_removed"],
        "copy_increases": card_delta["copy_increases"],
        "copy_decreases": card_delta["copy_decreases"],
        "role_package_deltas": collect_role_package_deltas(retest),
        "accepted_recommendations": accepted_recommendation_rows(retest),
        "rejected_recommendations": rejected_recommendation_rows(retest),
        "risk_flags": risk_flags,
        "human_review_notes": build_human_review_notes(card_delta, package_comparison, risk_flags, retest),
    }
    report["markdown"] = render_markdown(report)
    report["html"] = render_html(report)
    return report


def build_package_comparison(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(set(before) | set(after)):
        before_count = safe_int(before.get(key))
        after_count = safe_int(after.get(key))
        rows.append({"package": key, "baseline": before_count, "tuned": after_count, "delta": after_count - before_count})
    return rows


def build_card_delta(before_cards: list[Any], after_cards: list[Any]) -> dict[str, Any]:
    from collections import Counter

    before = Counter(str(card) for card in before_cards if str(card))
    after = Counter(str(card) for card in after_cards if str(card))
    names = sorted(set(before) | set(after))
    return {
        "cards_added": [name for name in names if before[name] == 0 and after[name] > 0],
        "cards_removed": [name for name in names if before[name] > 0 and after[name] == 0],
        "copy_increases": {name: after[name] - before[name] for name in names if after[name] > before[name]},
        "copy_decreases": {name: before[name] - after[name] for name in names if before[name] > after[name]},
    }


def collect_role_package_deltas(retest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, replay in iter_replay_reports(retest):
        for package, delta in (replay.get("package_gains_losses", {}) or {}).items():
            rows.append({"source": label, "package": package, "delta": delta})
    return rows


def collect_risk_flags(retest: dict[str, Any]) -> list[str]:
    flags = []
    for _label, replay in iter_replay_reports(retest):
        flags.extend(str(flag) for flag in replay.get("risk_flags", []) or [])
    return sorted(set(flags))


def accepted_recommendation_rows(retest: dict[str, Any]) -> list[dict[str, Any]]:
    accepted = retest.get("accepted_recommendation") or {}
    if not accepted:
        return []
    return [
        {
            "reason": accepted.get("reason", ""),
            "score": accepted.get("score", 0),
            "improvement": accepted.get("improvement", 0),
            "ratio_profile": accepted.get("ratio_profile", {}),
            "explanation": accepted.get("decision_explanation", ""),
        }
    ]


def rejected_recommendation_rows(retest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in retest.get("rejected_recommendations", []) or []:
        rows.append(
            {
                "reason": row.get("recommendation", {}).get("reason", ""),
                "score": row.get("score", 0),
                "improvement": row.get("improvement", 0),
                "rejection_reason": row.get("rejection_reason", ""),
                "explanation": row.get("card_shift_explanation", {}).get("explanation", ""),
            }
        )
    return rows


def iter_replay_reports(retest: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    accepted = (retest.get("accepted_recommendation") or {}).get("package_replay_report", {})
    if accepted:
        rows.append(("accepted", accepted))
    for index, rejected in enumerate(retest.get("rejected_recommendations", []) or [], start=1):
        replay = rejected.get("package_replay_report", {})
        if replay:
            rows.append((f"rejected_{index}", replay))
    return rows


def build_human_review_notes(card_delta: dict[str, Any], package_rows: list[dict[str, Any]], risk_flags: list[str], retest: dict[str, Any]) -> list[str]:
    notes = []
    if card_delta["cards_added"] or card_delta["cards_removed"]:
        notes.append("Review baseline-to-tuned card movement before trusting ratio memory.")
    negative_packages = [row for row in package_rows if row["delta"] < 0 and row["package"] in {"starters_searchers", "extenders", "interruptions", "board_breakers"}]
    if negative_packages:
        notes.append("Tuned build reduced at least one access, extender, interaction, or board-breaker package.")
    if risk_flags:
        notes.append(f"Targeted retests raised risk flags: {', '.join(risk_flags[:5])}.")
    if retest.get("targeted_retest_used") and not retest.get("accepted_recommendation"):
        notes.append("No targeted recommendation beat the stored safe baseline; inspect rejected replay sections.")
    if not notes:
        notes.append("No major review warnings detected.")
    return notes


def render_markdown(report: dict[str, Any]) -> str:
    score = report["score_summary"]
    lines = [
        f"# {report['archetype']} Deck Diff Review",
        "",
        "## Score Summary",
        "",
        "| Metric | Baseline | Tuned | Delta |",
        "|---|---:|---:|---:|",
        f"| Score | {score['baseline_score']} | {score['tuned_score']} | {score['score_delta']} |",
        f"| Confidence | {score['baseline_confidence']} | {score['tuned_confidence']} | {score['confidence_delta']} |",
        "",
        "## Baseline Deck",
        "",
        render_deck_sections(report.get("baseline_deck_sections", {})),
        "",
        "## Tuned Deck",
        "",
        render_deck_sections(report.get("tuned_deck_sections", {})),
        "",
        "## Package Count Comparison",
        "",
        "| Package | Baseline | Tuned | Delta |",
        "|---|---:|---:|---:|",
    ]
    for row in report.get("package_count_comparison", []):
        lines.append(f"| {row['package']} | {row['baseline']} | {row['tuned']} | {row['delta']:+d} |")
    lines.extend(["", "## Cards Added", ""])
    lines.extend(markdown_list(report.get("cards_added", [])))
    lines.extend(["", "## Cards Removed", ""])
    lines.extend(markdown_list(report.get("cards_removed", [])))
    lines.extend(["", "## Copy Changes", "", "| Card | Increase | Decrease |", "|---|---:|---:|"])
    copy_names = sorted(set(report.get("copy_increases", {})) | set(report.get("copy_decreases", {})))
    if copy_names:
        for name in copy_names:
            lines.append(f"| {name} | {report.get('copy_increases', {}).get(name, 0)} | {report.get('copy_decreases', {}).get(name, 0)} |")
    else:
        lines.append("| None | 0 | 0 |")
    lines.extend(["", "## Repair Actions", "", "### Baseline", ""])
    lines.extend(markdown_list(report.get("repair_actions", {}).get("baseline", [])))
    lines.extend(["", "### Tuned", ""])
    lines.extend(markdown_list(report.get("repair_actions", {}).get("tuned", [])))
    lines.extend(["", "## Accepted Recommendations", ""])
    lines.extend(recommendation_markdown(report.get("accepted_recommendations", [])))
    lines.extend(["", "## Rejected Recommendations", ""])
    lines.extend(recommendation_markdown(report.get("rejected_recommendations", [])[:8]))
    lines.extend(["", "## Risk Flags", ""])
    lines.extend(markdown_list(report.get("risk_flags", [])))
    lines.extend(["", "## Human Review Notes", ""])
    lines.extend(markdown_list(report.get("human_review_notes", [])))
    return "\n".join(lines) + "\n"


def render_deck_sections(sections: dict[str, Any]) -> str:
    lines = []
    for section in ("main", "extra"):
        cards = sections.get(section, []) if isinstance(sections, dict) else []
        lines.append(f"### {section.title()} ({len(cards)})")
        lines.append("")
        lines.extend(markdown_list(cards[:80]))
        lines.append("")
    return "\n".join(lines).strip()


def recommendation_markdown(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["- None"]
    lines = []
    for row in rows:
        label = row.get("rejection_reason") or "accepted"
        lines.append(f"- {label}: score {row.get('score', 0)}, delta {row.get('improvement', 0)}. {row.get('explanation', '')}")
    return lines


def markdown_list(values: list[Any]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]


def render_html(report: dict[str, Any]) -> str:
    markdown = render_markdown(report)
    body = "\n".join(f"<p>{escape(line)}</p>" if line and not line.startswith("#") else f"<h2>{escape(line.lstrip('# ').strip())}</h2>" for line in markdown.splitlines())
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Deck Diff Review</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:32px auto;line-height:1.4}"
        "p{margin:4px 0} h2{border-bottom:1px solid #ddd;padding-bottom:4px}"
        "</style></head><body>"
        f"{body}</body></html>\n"
    )


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
