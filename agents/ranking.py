"""Stable action-aware candidate ranking."""
ACTION_ORDER = {"SHORTLIST": 0, "REQUEST_INFO": 1, "HUMAN_REVIEW": 2, "LOW_MATCH": 3}

def recommendation(candidate):
    # A human decision completes the workflow, not the evidence ranking.
    result = candidate.get("evaluation", candidate)
    action = candidate.get("action", result.get("action"))
    return result.get("action") if action == "COMPLETE" else action

def rank_candidates(candidates):
    provisional = any(recommendation(c) in ("REQUEST_INFO", "HUMAN_REVIEW") for c in candidates)
    def key(candidate):
        result = candidate.get("evaluation", candidate); action = recommendation(candidate)
        documented = result.get("documented_score"); completeness = result.get("evidence_completeness")
        return (ACTION_ORDER.get(action, 99), -(documented if documented is not None else -1), -(completeness if completeness is not None else -1), candidate.get("id", result.get("candidate_id", "")))
    ordered = sorted(candidates, key=key)
    for rank, candidate in enumerate(ordered, 1):
        result = candidate.get("evaluation", candidate); result["rank"] = rank; result["rank_status"] = "provisional" if provisional else "final"
    return ordered
