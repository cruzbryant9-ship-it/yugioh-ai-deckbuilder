from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from deck import advisory_influence_budget as budget_module
import deck.generic_filler_selector as selector
from deck.generic_filler_selector import select_contextual_fillers
from generic_archetype_benchmark import run_benchmark
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root


ROOT = Path(__file__).resolve().parent


def main() -> None:
    with TemporaryDirectory(prefix="phase6t_gate_") as folder:
        gate_path = Path(folder) / "phase6t_gate_report.json"
        write_gate_report(gate_path)
        previous_path = selector.FILLER_GATE_REPORT_PATH
        previous_enabled = budget_module.ENABLE_FILLER_MEMORY_INFLUENCE
        previous_kill = budget_module.ADVISORY_KILL_SWITCH
        try:
            selector.FILLER_GATE_REPORT_PATH = gate_path
            checks = [
                ("default influence is off", validate_default_off),
                ("kill switch disables influence", validate_kill_switch),
                ("only activation-ready fillers receive influence", validate_allowed_only),
                ("Nibiru does not receive influence", validate_nibiru_blocked),
                ("Infinite Impermanence does not receive influence", validate_imperm_blocked),
                ("blocked cards cannot be selected", validate_blocked_card_not_selected),
                ("influence is capped", validate_bias_cap),
                ("influence can only apply small ordering bias", validate_small_ordering_bias),
                ("A/B benchmark runs", validate_ab_benchmark_runs),
                ("Phase 6S validator still passes", validate_phase6s_still_passes),
                ("matchup matrix smoke still passes", validate_matrix_smoke),
            ]
            failures = []
            for label, check in checks:
                try:
                    check()
                    print(f"PASS: {label}")
                except Exception as exc:
                    failures.append(label)
                    print(f"FAIL: {label}: {exc}")
            if failures:
                raise SystemExit(1)
            print_sample()
            print("Phase 6T validation complete.")
        finally:
            selector.FILLER_GATE_REPORT_PATH = previous_path
            budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = previous_enabled
            budget_module.ADVISORY_KILL_SWITCH = previous_kill


def validate_default_off() -> None:
    budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = False
    budget_module.ADVISORY_KILL_SWITCH = False
    result = select_contextual_fillers("Probe", "meta", 1, probe_card_pool(), probe_deck(39), {"interruptions": 1}, enable_filler_memory_influence=False)
    state = result.get("filler_memory_influence", {})
    if state.get("enabled") or state.get("filler_memory_bias_applied"):
        raise AssertionError(state)


def validate_kill_switch() -> None:
    budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = True
    budget_module.ADVISORY_KILL_SWITCH = True
    result = select_contextual_fillers("Probe", "meta", 1, probe_card_pool(), probe_deck(39), {"interruptions": 1}, enable_filler_memory_influence=True)
    state = result.get("filler_memory_influence", {})
    if state.get("enabled") or state.get("filler_memory_bias_applied"):
        raise AssertionError(state)
    budget_module.ADVISORY_KILL_SWITCH = False


def validate_allowed_only() -> None:
    state = influenced_selector_state()
    applied = set(state.get("filler_memory_bias_applied", {}))
    if not applied:
        raise AssertionError(state)
    if not applied <= {"Ash Blossom & Joyous Spring", "Effect Veiler", "Ghost Belle & Haunted Mansion"}:
        raise AssertionError(state)


def validate_nibiru_blocked() -> None:
    state = influenced_selector_state()
    if "Nibiru, the Primal Being" in state.get("filler_memory_bias_applied", {}):
        raise AssertionError(state)
    if "Nibiru, the Primal Being" not in state.get("fillers_blocked_from_influence", []):
        raise AssertionError(state)
    if "Nibiru, the Primal Being" in influenced_selector_result().get("selected_fillers", []):
        raise AssertionError("Nibiru was selected with influence enabled")


def validate_imperm_blocked() -> None:
    state = influenced_selector_state()
    if "Infinite Impermanence" in state.get("filler_memory_bias_applied", {}):
        raise AssertionError(state)
    if "Infinite Impermanence" not in state.get("fillers_blocked_from_influence", []):
        raise AssertionError(state)
    if "Infinite Impermanence" in influenced_selector_result().get("selected_fillers", []):
        raise AssertionError("Infinite Impermanence was selected with influence enabled")


def validate_blocked_card_not_selected() -> None:
    budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = True
    pool = [{"name": "Ash Blossom & Joyous Spring", "type": "Monster", "desc": "negate", "banlist_info": {"ban_tcg": "Forbidden"}}]
    result = select_contextual_fillers("Probe", "meta", 1, pool, probe_deck(39), {"interruptions": 1}, enable_filler_memory_influence=True)
    if "Ash Blossom & Joyous Spring" in result.get("selected_fillers", []):
        raise AssertionError(result)


def validate_bias_cap() -> None:
    state = influenced_selector_state()
    total = sum(abs(float(value or 0)) for value in state.get("filler_memory_bias_applied", {}).values())
    if total > budget_module.MAX_FILLER_MEMORY_BIAS + 1e-9:
        raise AssertionError(state)
    if any(abs(float(value or 0)) > budget_module.PER_CARD_FILLER_MEMORY_BIAS_CAP + 1e-9 for value in state.get("filler_memory_bias_applied", {}).values()):
        raise AssertionError(state)


def validate_small_ordering_bias() -> None:
    budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = True
    result = select_contextual_fillers("Probe", "meta", 1, probe_card_pool(), probe_deck(39), {"interruptions": 1}, enable_filler_memory_influence=True)
    state = result.get("filler_memory_influence", {})
    if state.get("enabled") and sum(abs(float(value or 0)) for value in state.get("filler_memory_bias_applied", {}).values()) > 0.030001:
        raise AssertionError(state)


def validate_ab_benchmark_runs() -> None:
    provenance = provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True)
    with temporary_isolated_memory_root("phase6t_ab_"):
        off = run_benchmark(["Runick"], mode="meta", runs=1, provenance=provenance, enable_filler_memory_influence=False)
        on = run_benchmark(["Runick"], mode="meta", runs=1, provenance=provenance, enable_filler_memory_influence=True)
    if off.get("summary", {}).get("filler_memory_influence_enabled"):
        raise AssertionError(off.get("summary", {}))
    if not on.get("summary", {}).get("filler_memory_influence_enabled"):
        raise AssertionError(on.get("summary", {}))


def validate_phase6s_still_passes() -> None:
    import validate_phase6s as phase6s

    phase6s.validate_eligible_signals_loaded()
    phase6s.validate_holdout_review_runs()
    phase6s.validate_counts_recorded()
    phase6s.validate_failed_holdout_not_activation_ready()
    phase6s.validate_filler_influence_disabled()


def validate_matrix_smoke() -> None:
    output = run_command(
        "matchup_matrix.py",
        "--archetype",
        "Blue-Eyes",
        "--mode",
        "meta",
        "--runs-per-cell",
        "1",
        "--use-curated-opponents",
        "--smoke",
        timeout=1800,
    )
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def influenced_selector_state() -> dict[str, Any]:
    return influenced_selector_result().get("filler_memory_influence", {})


def influenced_selector_result() -> dict[str, Any]:
    budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = True
    budget_module.ADVISORY_KILL_SWITCH = False
    return select_contextual_fillers("Probe", "meta", 1, probe_card_pool(), probe_deck(39), {"interruptions": 1}, enable_filler_memory_influence=True)


def probe_card_pool() -> list[dict[str, Any]]:
    return [
        {"name": "Ash Blossom & Joyous Spring", "type": "Monster", "desc": "negate"},
        {"name": "Effect Veiler", "type": "Monster", "desc": "negate"},
        {"name": "Ghost Belle & Haunted Mansion", "type": "Monster", "desc": "negate"},
        {"name": "Nibiru, the Primal Being", "type": "Monster", "desc": "special summon"},
        {"name": "Infinite Impermanence", "type": "Trap Card", "desc": "negate"},
        {"name": "Droll & Lock Bird", "type": "Monster", "desc": "negate"},
    ]


def probe_deck(count: int) -> list[dict[str, Any]]:
    return [{"name": f"Probe Card {index}", "type": "Spell Card", "desc": "probe"} for index in range(count)]


def write_gate_report(path: Path) -> None:
    rows = []
    for name, holdout in {
        "Ash Blossom & Joyous Spring": True,
        "Effect Veiler": True,
        "Ghost Belle & Haunted Mansion": True,
        "Nibiru, the Primal Being": False,
        "Infinite Impermanence": False,
    }.items():
        rows.append({"card": name, "eligible": True, "holdout_passed": holdout, "activation_ready": holdout})
    atomic_write_json(
        path,
        {
            "summary": {
                "activation_ready_fillers": ["Ash Blossom & Joyous Spring", "Effect Veiler", "Ghost Belle & Haunted Mansion"],
                "activation_ready_count": 3,
            },
            "eligible_signals": rows,
        },
    )


def run_command(*args: str, timeout: int = 600) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout[-4000:])
    return result.stdout


def print_sample() -> None:
    state = influenced_selector_state()
    print("Sample allowed fillers:", state.get("fillers_allowed_for_influence", []))
    print("Sample blocked fillers:", state.get("fillers_blocked_from_influence", []))
    print("Sample applied bias:", state.get("filler_memory_bias_applied", {}))


if __name__ == "__main__":
    main()
