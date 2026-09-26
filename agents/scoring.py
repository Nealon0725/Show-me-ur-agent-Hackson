"""Deterministic scoring for confirmed screening evidence."""
RESOLVED = {"evidenced", "not_met"}
POSSIBLE = {"evidenced", "unknown", "needs_review"}

def calculate_scores(details):
    scored = [item for item in details if item.get("scored", True)]
    total = sum(item.get("weight", 0) for item in scored)
    if not total:
        return {"documented_score": None, "possible_score": None, "evidence_completeness": None}
    def pct(statuses):
        value = sum(item.get("weight", 0) for item in scored if item.get("status") in statuses)
        return round(100 * value / total)
    return {"documented_score": pct({"evidenced"}), "possible_score": pct(POSSIBLE), "evidence_completeness": pct(RESOLVED)}
