"""Deterministic next-action policy. Recommendations are never hiring decisions."""
def decide_action(details, followup_round=0):
    if any(item.get("status") == "needs_review" for item in details): return "HUMAN_REVIEW"
    if any(item.get("required") and item.get("status") == "not_met" for item in details): return "LOW_MATCH"
    if any(item.get("required") and item.get("status") == "unknown" for item in details):
        return "REQUEST_INFO" if followup_round < 2 else "HUMAN_REVIEW"
    return "SHORTLIST"
