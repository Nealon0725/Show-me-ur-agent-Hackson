"""Criterion-specific clarification questions for unknown evidence only."""
def generate_questions(details, followup_round=0):
    if followup_round >= 2: return []
    return [{"criterion_id": item["id"], "question": "Could you describe your %s, including a concrete task and approximate dates?" % item.get("description", item.get("label", item["id"]))} for item in details if item.get("status") == "unknown"]
