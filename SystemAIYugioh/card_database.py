from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json

YGOPRODECK_CARDINFO_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_REFRESH_INTERVAL_SECONDS = 6 * 60 * 60
META_SCORE_THRESHOLD = 55

LIMITED_STATUSES = {"Forbidden": 0, "Limited": 1, "Semi-Limited": 2}
GENERIC_SYNERGY_TERMS = {
    "draw",
    "search",
    "add",
    "special summon",
    "send",
    "destroy",
    "negate",
    "banish",
    "graveyard",
    "deck",
    "extra deck",
}


class CardDatabase:
    """Maintains local YGOPRODeck snapshots and update intelligence."""

    def __init__(
        self,
        data_dir: Path | str = DEFAULT_DATA_DIR,
        refresh_interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.snapshots_dir = self.data_dir / "snapshots"
        self.profiles_dir = self.data_dir / "deck_profiles"
        self.cards_path = self.data_dir / "cards.json"
        self.metadata_path = self.data_dir / "metadata.json"
        self.analysis_path = self.data_dir / "latest_update_analysis.json"
        self.refresh_interval_seconds = refresh_interval_seconds

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def load_cards(self) -> list[dict[str, Any]]:
        return self._read_json(self.cards_path, [])

    def load_metadata(self) -> dict[str, Any]:
        return self._read_json(self.metadata_path, {})

    def refresh_on_startup(self, force: bool = False) -> dict[str, Any]:
        metadata = self.load_metadata()
        last_sync = float(metadata.get("last_sync_epoch", 0))
        stale = time.time() - last_sync >= self.refresh_interval_seconds
        if force or stale or not self.cards_path.exists():
            return self.sync()

        analysis = self._read_json(self.analysis_path, {})
        analysis.setdefault("sync_skipped", True)
        analysis.setdefault("reason", "Local card database is still fresh.")
        return analysis

    def sync(self) -> dict[str, Any]:
        self.ensure_dirs()
        previous_cards = self.load_cards()
        latest_cards = self.fetch_cards()
        analysis = self.analyze_update(previous_cards, latest_cards)

        snapshot_path = self.write_snapshot(latest_cards)
        self._write_json(self.cards_path, latest_cards)

        metadata = {
            "last_sync_utc": self._utc_now(),
            "last_sync_epoch": time.time(),
            "source": YGOPRODECK_CARDINFO_URL,
            "card_count": len(latest_cards),
            "latest_snapshot": str(snapshot_path),
            "database_hash": self._stable_hash(latest_cards),
        }
        self._write_json(self.metadata_path, metadata)
        self._write_json(self.analysis_path, analysis)
        self.update_deck_profiles(analysis)
        return analysis

    def fetch_cards(self) -> list[dict[str, Any]]:
        request = Request(YGOPRODECK_CARDINFO_URL, headers={"User-Agent": "yugioh-ai-deckbuilder/1.0"})
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError(f"Unable to sync YGOPRODeck data: {exc}") from exc

        cards = payload.get("data")
        if not isinstance(cards, list):
            raise RuntimeError("YGOPRODeck response did not include a card data list.")
        return cards

    def write_snapshot(self, cards: list[dict[str, Any]]) -> Path:
        snapshot_name = f"cards_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        snapshot_path = self.snapshots_dir / snapshot_name
        self._write_json(snapshot_path, cards)
        return snapshot_path

    def analyze_update(
        self,
        old_cards: list[dict[str, Any]],
        new_cards: list[dict[str, Any]],
    ) -> dict[str, Any]:
        old_by_id = {str(card.get("id")): card for card in old_cards if card.get("id") is not None}
        new_by_id = {str(card.get("id")): card for card in new_cards if card.get("id") is not None}
        old_archetypes = self.archetype_map(old_cards)
        new_archetypes = self.archetype_map(new_cards)

        added = [new_by_id[card_id] for card_id in sorted(set(new_by_id) - set(old_by_id))]
        removed = [old_by_id[card_id] for card_id in sorted(set(old_by_id) - set(new_by_id))]
        changed_limits = self.detect_banlist_changes(old_by_id, new_by_id)
        new_archetype_names = sorted(set(new_archetypes) - set(old_archetypes))
        support = self.detect_new_support(added, old_archetypes)
        synergy = self.discover_synergy(added, old_archetypes)
        flagged = self.flag_meta_relevant_cards(added, support, synergy)

        affected_archetypes = sorted(
            set(new_archetype_names)
            | set(support)
            | {item["archetype"] for item in synergy}
            | {change["archetype"] for change in changed_limits if change.get("archetype")}
        )

        return {
            "generated_at_utc": self._utc_now(),
            "old_card_count": len(old_cards),
            "new_card_count": len(new_cards),
            "new_cards": [self.card_summary(card) for card in added],
            "removed_cards": [self.card_summary(card) for card in removed],
            "new_archetypes": new_archetype_names,
            "new_support": {
                archetype: [self.card_summary(card) for card in cards]
                for archetype, cards in sorted(support.items())
            },
            "banlist_changes": changed_limits,
            "potentially_meta_relevant_cards": flagged,
            "synergy_candidates": synergy[:100],
            "archetypes_to_rescore": affected_archetypes,
            "deck_profiles_to_rescore": self.deck_profiles_to_rescore(affected_archetypes),
        }

    def archetype_map(self, cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        archetypes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for card in cards:
            archetype = card.get("archetype")
            if archetype:
                archetypes[str(archetype)].append(card)
        return dict(archetypes)

    def detect_new_support(
        self,
        added_cards: list[dict[str, Any]],
        existing_archetypes: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        support: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for card in added_cards:
            card_archetype = card.get("archetype")
            if card_archetype in existing_archetypes:
                support[str(card_archetype)].append(card)
                continue

            text = self.search_text(card)
            for archetype in existing_archetypes:
                if archetype.lower() in text:
                    support[archetype].append(card)
        return dict(support)

    def detect_banlist_changes(
        self,
        old_by_id: dict[str, dict[str, Any]],
        new_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        changes = []
        for card_id in sorted(set(old_by_id) & set(new_by_id)):
            old_card = old_by_id[card_id]
            new_card = new_by_id[card_id]
            old_limit = self.card_limit_status(old_card)
            new_limit = self.card_limit_status(new_card)
            if old_limit != new_limit:
                changes.append(
                    {
                        "id": new_card.get("id"),
                        "name": new_card.get("name"),
                        "archetype": new_card.get("archetype"),
                        "old_status": old_limit,
                        "new_status": new_limit,
                        "old_max_copies": LIMITED_STATUSES.get(old_limit, 3),
                        "new_max_copies": LIMITED_STATUSES.get(new_limit, 3),
                    }
                )
        return changes

    def discover_synergy(
        self,
        added_cards: list[dict[str, Any]],
        existing_archetypes: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        candidates = []
        archetype_traits = {
            name: self.archetype_traits(cards) for name, cards in existing_archetypes.items()
        }
        for card in added_cards:
            card_text = self.search_text(card)
            card_tokens = self.tokenize(card_text)
            for archetype, traits in archetype_traits.items():
                overlap = sorted((card_tokens & traits["tokens"]) - set(archetype.lower().split()))
                score = len(overlap) * 4
                score += sum(12 for term in GENERIC_SYNERGY_TERMS if term in card_text)
                score += 20 if archetype.lower() in card_text else 0
                if score >= 20:
                    candidates.append(
                        {
                            "card": self.card_summary(card),
                            "archetype": archetype,
                            "score": score,
                            "shared_terms": overlap[:12],
                        }
                    )
        return sorted(candidates, key=lambda item: item["score"], reverse=True)

    def flag_meta_relevant_cards(
        self,
        added_cards: list[dict[str, Any]],
        support: dict[str, list[dict[str, Any]]],
        synergy: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        support_ids = {str(card.get("id")) for cards in support.values() for card in cards}
        synergy_scores: dict[str, int] = defaultdict(int)
        for item in synergy:
            card_id = str(item["card"].get("id"))
            synergy_scores[card_id] = max(synergy_scores[card_id], int(item["score"]))

        flagged = []
        for card in added_cards:
            card_id = str(card.get("id"))
            score, reasons = self.meta_relevance_score(card)
            if card_id in support_ids:
                score += 20
                reasons.append("supports an existing archetype")
            if synergy_scores[card_id]:
                score += min(30, synergy_scores[card_id] // 2)
                reasons.append("has high text overlap with known archetype gameplans")
            if score >= META_SCORE_THRESHOLD:
                summary = self.card_summary(card)
                summary["meta_score"] = score
                summary["reasons"] = reasons
                flagged.append(summary)
        return sorted(flagged, key=lambda card: card["meta_score"], reverse=True)

    def meta_relevance_score(self, card: dict[str, Any]) -> tuple[int, list[str]]:
        text = self.search_text(card)
        score = 0
        reasons = []
        weighted_terms = {
            "negate": 18,
            "cannot be negated": 16,
            "special summon": 12,
            "add": 10,
            "draw": 10,
            "send": 8,
            "banish": 8,
            "destroy": 6,
            "quick effect": 18,
            "once per turn": 4,
            "from your deck": 14,
            "extra deck": 8,
        }
        for term, weight in weighted_terms.items():
            if term in text:
                score += weight
                reasons.append(f"contains '{term}'")

        card_type = str(card.get("type", "")).lower()
        if "link" in card_type or "xyz" in card_type or "synchro" in card_type or "fusion" in card_type:
            score += 8
            reasons.append("extra deck monster")
        if card.get("archetype"):
            score += 5
            reasons.append("archetype card")
        return score, reasons

    def update_deck_profiles(self, analysis: dict[str, Any]) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.profiles_dir / "rescore_queue.json"
        queue = self._read_json(index_path, [])
        queued_keys = {item.get("key") for item in queue if isinstance(item, dict)}
        now = self._utc_now()

        for archetype in analysis.get("archetypes_to_rescore", []):
            key = f"archetype:{archetype}"
            if key not in queued_keys:
                queue.append(
                    {
                        "key": key,
                        "archetype": archetype,
                        "reason": "New cards, support, synergy, or banlist changes may alter strength.",
                        "queued_at_utc": now,
                        "status": "pending",
                    }
                )
        self._write_json(index_path, queue)

    def deck_profiles_to_rescore(self, archetypes: list[str]) -> list[str]:
        profiles = []
        if not self.profiles_dir.exists():
            return profiles
        archetype_set = {name.lower() for name in archetypes}
        for path in self.profiles_dir.glob("*.json"):
            profile = self._read_json(path, {})
            if not isinstance(profile, dict):
                continue
            profile_archetype = str(profile.get("archetype", "")).lower()
            profile_cards = " ".join(profile.get("cards", [])).lower() if isinstance(profile.get("cards"), list) else ""
            if profile_archetype in archetype_set or any(name in profile_cards for name in archetype_set):
                profiles.append(path.stem)
        return profiles

    def record_card_performance(
        self,
        card_name: str,
        wins: int,
        games: int,
        deck_archetype: str | None = None,
    ) -> dict[str, Any]:
        performance_path = self.data_dir / "card_performance.json"
        performance = self._read_json(performance_path, {})
        record = performance.setdefault(
            card_name,
            {"wins": 0, "games": 0, "archetypes": {}, "updated_at_utc": None},
        )
        record["wins"] += wins
        record["games"] += games
        if deck_archetype:
            archetype_record = record["archetypes"].setdefault(deck_archetype, {"wins": 0, "games": 0})
            archetype_record["wins"] += wins
            archetype_record["games"] += games
        record["win_rate"] = round(record["wins"] / record["games"], 4) if record["games"] else 0
        record["updated_at_utc"] = self._utc_now()
        self._write_json(performance_path, performance)
        return record

    def archetype_traits(self, cards: list[dict[str, Any]]) -> dict[str, set[str]]:
        text = " ".join(self.search_text(card) for card in cards)
        token_counts = Counter(self.tokenize(text))
        return {"tokens": {token for token, count in token_counts.items() if count >= 2}}

    def card_limit_status(self, card: dict[str, Any]) -> str:
        ban_info = card.get("banlist_info") or {}
        return ban_info.get("ban_tcg") or "Unlimited"

    def card_summary(self, card: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": card.get("id"),
            "name": card.get("name"),
            "type": card.get("type"),
            "archetype": card.get("archetype"),
            "race": card.get("race"),
            "attribute": card.get("attribute"),
            "ban_tcg": (card.get("banlist_info") or {}).get("ban_tcg", "Unlimited"),
        }

    def search_text(self, card: dict[str, Any]) -> str:
        parts = [
            str(card.get("name", "")),
            str(card.get("type", "")),
            str(card.get("race", "")),
            str(card.get("attribute", "")),
            str(card.get("archetype", "")),
            str(card.get("desc", "")),
        ]
        return " ".join(parts).lower()

    def tokenize(self, text: str) -> set[str]:
        stopwords = {
            "the",
            "and",
            "you",
            "your",
            "this",
            "that",
            "from",
            "with",
            "card",
            "cards",
            "monster",
            "monsters",
            "spell",
            "trap",
            "effect",
            "turn",
            "can",
            "per",
            "one",
        }
        return {token for token in re.findall(r"[a-z0-9-]{3,}", text.lower()) if token not in stopwords}

    def _read_json(self, path: Path, default: Any) -> Any:
        return safe_load_json(path, default)

    def _write_json(self, path: Path, data: Any) -> None:
        atomic_write_json(path, data)

    def _stable_hash(self, data: Any) -> str:
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Sync and analyze the live Yu-Gi-Oh card database.")
    parser.add_argument("--force", action="store_true", help="Force a YGOPRODeck sync even if local data is fresh.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=int(os.environ.get("YGO_REFRESH_INTERVAL_SECONDS", DEFAULT_REFRESH_INTERVAL_SECONDS)),
        help="Minimum age before startup refresh performs another API sync.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full update analysis JSON.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep running and refresh on the configured interval.",
    )
    args = parser.parse_args()

    database = CardDatabase(refresh_interval_seconds=args.interval_seconds)

    while True:
        analysis = database.refresh_on_startup(force=args.force)
        print_analysis_summary(database, analysis, full_json=args.json)
        if not args.watch:
            break
        args.force = False
        time.sleep(args.interval_seconds)


def print_analysis_summary(database: CardDatabase, analysis: dict[str, Any], full_json: bool = False) -> None:
    if full_json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return

    if analysis.get("sync_skipped"):
        print("YGOPRODeck sync skipped; local database is still fresh.")
    else:
        print("YGOPRODeck sync complete.")
    print(f"Cards: {analysis.get('new_card_count', 0)}")
    print(f"New cards detected: {len(analysis.get('new_cards', []))}")
    print(f"New archetypes detected: {len(analysis.get('new_archetypes', []))}")
    print(f"Banlist changes detected: {len(analysis.get('banlist_changes', []))}")
    print(f"Meta-relevant cards flagged: {len(analysis.get('potentially_meta_relevant_cards', []))}")
    print(f"Archetypes queued for re-score: {len(analysis.get('archetypes_to_rescore', []))}")
    print(f"Full analysis: {database.analysis_path}")


if __name__ == "__main__":
    main()
