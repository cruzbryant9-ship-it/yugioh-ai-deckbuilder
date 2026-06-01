from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from SystemAIYugioh.card_database import CardDatabase
from deck.archetype_relationship_graph import build_archetype_relationship_graph, score_archetype_compatibility
from deck.archetype_role_inference import infer_archetype_roles
from deck.generic_combo_skeleton import infer_combo_skeletons
from deck.generic_package_extractor import extract_generic_packages

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("unseen archetype can be analyzed", lambda: validate_unseen_archetype(cards)),
        ("package extraction works on non-Blue-Eyes archetype", lambda: validate_package_extraction(cards)),
        ("role inference produces stable outputs", lambda: validate_stable_roles(cards)),
        ("generalized combo skeletons can be inferred", lambda: validate_combo_skeleton(cards)),
        ("compatibility scoring runs", lambda: validate_compatibility(cards)),
        ("matchup matrix still works", validate_matrix_smoke),
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
    print_sample_outputs(cards)
    print("Phase 6A validation complete.")


def validate_unseen_archetype(cards: list[dict]) -> None:
    analysis = infer_archetype_roles(cards, "Branded")
    if analysis["card_count"] < 3:
        raise AssertionError(analysis["card_count"])
    if not analysis["roles"].get("starter") and not analysis["roles"].get("searcher"):
        raise AssertionError(analysis["role_counts"])


def validate_package_extraction(cards: list[dict]) -> None:
    packages = extract_generic_packages(cards, "Branded")
    package_types = {package["package_type"] for package in packages["packages"]}
    if not {"starters", "engine"} & package_types:
        raise AssertionError(package_types)
    if packages["analysis"]["archetype"] != "Branded":
        raise AssertionError(packages)


def validate_stable_roles(cards: list[dict]) -> None:
    first = infer_archetype_roles(cards, "Kashtira")
    second = infer_archetype_roles(cards, "Kashtira")
    if first["role_counts"] != second["role_counts"]:
        raise AssertionError((first["role_counts"], second["role_counts"]))
    if first["roles"] != second["roles"]:
        raise AssertionError("role lists drifted")


def validate_combo_skeleton(cards: list[dict]) -> None:
    skeletons = infer_combo_skeletons(cards, "Branded")
    if skeletons["skeleton_count"] < 1:
        raise AssertionError(skeletons["role_counts"])
    first = skeletons["skeletons"][0]
    for key in ("starter", "payoff", "skeleton", "confidence"):
        if key not in first:
            raise AssertionError(first)


def validate_compatibility(cards: list[dict]) -> None:
    score = score_archetype_compatibility(cards, "Blue-Eyes", "Bystial")
    if not 0 <= score["final_compatibility_score"] <= 1:
        raise AssertionError(score)
    graph = build_archetype_relationship_graph(cards, ["Blue-Eyes", "Bystial", "Branded"])
    if graph["edge_count"] != 3 or not graph["edges"]:
        raise AssertionError(graph)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def print_sample_outputs(cards: list[dict]) -> None:
    branded = infer_archetype_roles(cards, "Branded")
    packages = extract_generic_packages(cards, "Branded")
    skeletons = infer_combo_skeletons(cards, "Branded")
    compatibility = score_archetype_compatibility(cards, "Blue-Eyes", "Bystial")
    print("SAMPLE: Branded role counts:", branded["role_counts"])
    print("SAMPLE: Branded package types:", [package["package_type"] for package in packages["packages"][:5]])
    print("SAMPLE: Branded first skeleton:", skeletons["skeletons"][0] if skeletons["skeletons"] else {})
    print("SAMPLE: Blue-Eyes/Bystial compatibility:", compatibility)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
