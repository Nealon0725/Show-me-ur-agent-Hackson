"""Compose confirmed evidence into deterministic scores, explanations and next actions."""
from agents.parsers import parse_resume
from agents.scoring import calculate_scores
from agents.action_policy import decide_action
from agents.followup import generate_questions

def evaluate(text, criteria, answers=None, resume_parser=None, followup_round=0, candidate_id=None, criteria_version=1):
    profile = (resume_parser or parse_resume)(text, criteria)
    return evaluate_profile(profile, criteria, answers, followup_round, candidate_id, criteria_version)


def evaluate_profile(profile, criteria, answers=None, followup_round=0, candidate_id=None, criteria_version=1):
    """Re-score saved evidence without calling the model again."""
    answers = answers or {}; details = []
    for criterion in criteria:
        fact = profile["facts"][criterion["id"]]
        if criterion["id"] in answers:
            answer = answers[criterion["id"]]
            fact = {"status": answer["status"], "evidence": ["Follow-up: " + answer["evidence"]], "evidence_refs": [{"source": "followup", "text": answer["evidence"], "line": None}], "resume_evidence_refs": fact["evidence_refs"], "reason": "Evidence status confirmed by the recruiter from a follow-up answer."}
        details.append(dict(criterion, **fact))
    scores = calculate_scores(details); action = decide_action(details, followup_round)
    strengths = [i["label"] for i in details if i["status"] == "evidenced"]; gaps = [i["label"] for i in details if i["status"] == "not_met"]
    missing = [i["label"] for i in details if i["status"] in ("unknown", "needs_review")]
    recommendation = {"SHORTLIST": "Documented required evidence supports progression to human shortlist review.", "REQUEST_INFO": "Potential match; clarification of required evidence is recommended.", "HUMAN_REVIEW": "Human review is required before any hiring decision.", "LOW_MATCH": "At least one required criterion is explicitly not met; human review is required before any rejection."}[action]
    return {"candidate_id": candidate_id, "criteria_version": criteria_version, **scores, "score": scores["documented_score"], "score_label": "Documented skill coverage (not hiring probability)", "details": details, "strengths": strengths, "gaps": gaps, "missing_information": missing, "questions": generate_questions(details, followup_round), "unmet_requirements": gaps, "recommendation": recommendation, "action": action, "parser": profile["parser"], "model_usage": profile.get("usage", {}), "model_request_id": profile.get("request_id"), "rank": None, "rank_status": None}
