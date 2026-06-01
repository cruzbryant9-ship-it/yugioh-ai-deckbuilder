from data.card_limits import get_custom_card_limit


def get_card_limit(card):
    custom_limit = get_custom_card_limit(card.get("name", ""))
    if custom_limit is not None:
        return custom_limit

    ban_info = card.get("banlist_info") or {}

    status = ban_info.get("ban_tcg")

    if status == "Forbidden":
        return 0
    elif status == "Limited":
        return 1
    elif status == "Semi-Limited":
        return 2
    else:
        return 3


def get_card_limit_status(card):
    ban_info = card.get("banlist_info") or {}
    return ban_info.get("ban_tcg") or "Unlimited"
