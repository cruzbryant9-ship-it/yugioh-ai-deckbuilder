from data.card_limits import startup_safety_cleanup
from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.matchup_profiles import get_matchup_profile
from deck.side_deck_planner import build_side_deck
from SystemAIYugioh.card_database import CardDatabase


def main():
    removed_stats = startup_safety_cleanup()
    if removed_stats:
        print(f"Removed {removed_stats} blocked card entries from learned memory")

    database = CardDatabase()
    try:
        analysis = database.refresh_on_startup()
        if not analysis.get("sync_skipped") and (analysis.get("new_cards") or analysis.get("banlist_changes")):
            print("Card database refreshed. Update analysis saved to SystemAIYugioh/data/latest_update_analysis.json")
    except RuntimeError as exc:
        print(exc)
        print("Using the latest local card database snapshot instead.")

    cards = database.load_cards()
    if not cards:
        print("No local card database found. Run: python fetch_cards.py --force")
        return

    archetype_name = input("Enter archetype name: ").strip()
    matchup_name = input("Matchup? [unknown_meta]: ").strip() or "unknown_meta"
    going = input("Going first/second/both? [both]: ").strip() or "both"
    tune_runs_text = input("Generic tune runs? [0]: ").strip() or "0"
    try:
        generic_tune_runs = max(0, int(tune_runs_text))
    except ValueError:
        generic_tune_runs = 0
    deck, archetype_cards = build_deck(cards, archetype_name, matchup=matchup_name, going=going, generic_tune_runs=generic_tune_runs)
    build_report = get_last_build_report()

    print(f"{archetype_name} archetype cards found:", len(archetype_cards))
    print(f"Builder used: {build_report.get('builder_used', 'unknown')}")
    if build_report.get("generic_confidence_score") is not None:
        print(f"Generic confidence score: {build_report.get('generic_confidence_score')}")
    if build_report.get("quota_warnings"):
        print("Quota warnings:", "; ".join(build_report["quota_warnings"]))
    if build_report.get("generic_tuning"):
        tuning = build_report["generic_tuning"]
        print(f"Generic tuning: best {tuning.get('best_score')}, average {tuning.get('average_score')}, memory updated {tuning.get('memory_updated')}")

    if not archetype_cards:
        print("No cards found for that archetype.")
        return

    if len(deck) < 40:
        print("Could not build a full 40 card legal deck from the available archetype pool.")
        print(f"Generated {len(deck)} cards instead.")

    print("\nGenerated Deck:\n")
    for card in deck:
        print(card["name"])

    side_report = build_side_deck(deck, archetype_name, get_matchup_profile(matchup_name), cards, going=going)
    print(f"\nSide Deck Recommendations ({side_report['matchup']}, going {going}):\n")
    for card in side_report["side_deck"]:
        print(card["name"])
    print("\nSide-In Reasoning:")
    for name, reasons in side_report["reasons"].items():
        print(f"{name}: {', '.join(reasons)}")
    print("\nGoing First Plan:")
    for item in side_report["going_first_plan"]:
        print(f"- {item}")
    print("\nGoing Second Plan:")
    for item in side_report["going_second_plan"]:
        print(f"- {item}")
    print("\nSuggested Side-Out Cards:")
    for name in side_report["cards_to_side_out"]:
        print(f"- {name}")

    score_breakdown = score_deck_breakdown(deck, archetype_name, "meta")
    print("\nScore Breakdown:\n")
    for key, value in score_breakdown.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
