"""Bounded evidence -> action -> follow-up -> re-evaluate -> human decision workflow."""
from agents.parsers import parse_jd, lines
from agents.screening import evaluate, evaluate_profile
from agents.ranking import rank_candidates
from tools.store import Store

ACTION_STATE = {"REQUEST_INFO": "REQUEST_INFO", "SHORTLIST": "SHORTLIST_REVIEW", "LOW_MATCH": "LOW_MATCH_REVIEW", "HUMAN_REVIEW": "HUMAN_REVIEW"}

class Workflow:
    def __init__(self, path, resume_parser=None):
        self.store = Store(path); self.resume_parser = resume_parser

    def create(self, jd, resumes):
        job = parse_jd(jd)
        job["criteria_version"] = 1
        if not isinstance(resumes, list) or not 1 <= len(resumes) <= 30: raise ValueError('Provide 1–30 resumes.')
        for resume in resumes: lines(resume)
        state = {"job": job, "criteria_confirmed": False, "workflow_state": "AWAITING_CRITERIA_CONFIRMATION", "events": [], "candidates": [{"id": "C%03d" % (i + 1), "text": text, "answers": {}, "round": 0, "action": "CONFIRM_CRITERIA", "state": "AWAITING_CRITERIA_CONFIRMATION", "decision": None} for i, text in enumerate(resumes)]}
        self.event(state, "JD_PARSED", None, "Human confirmation required before screening.")
        return self.store.create(state)

    @staticmethod
    def event(state, action, candidate_id=None, reason=""):
        state["events"].append({"step": len(state["events"]) + 1, "action": action, "candidate_id": candidate_id, "reason": reason, "detail": ((candidate_id + ": ") if candidate_id else "") + reason})

    def rerank(self, state): rank_candidates(state["candidates"])

    def get(self, run_id):
        state = self.store.get(run_id)
        state["job"].setdefault("criteria_version", 1)
        for candidate in state["candidates"]:
            if "state" in candidate:
                continue
            if not state["criteria_confirmed"]:
                candidate["state"] = "AWAITING_CRITERIA_CONFIRMATION"
                continue
            previous = candidate["evaluation"]
            profile = self.saved_profile(previous)
            result = evaluate_profile(profile, state["job"]["criteria"], candidate["answers"],
                                      candidate["round"], candidate["id"], state["job"]["criteria_version"])
            candidate["evaluation"] = result
            candidate["action"] = "COMPLETE" if candidate["decision"] else result["action"]
            candidate["state"] = "COMPLETE" if candidate["decision"] else ACTION_STATE[result["action"]]
        if state["criteria_confirmed"]:
            self.rerank(state)
        self.refresh_state(state)
        return state

    @staticmethod
    def saved_profile(result):
        facts = {}
        for item in result["details"]:
            fact = dict(item)
            fact["evidence_refs"] = item.get("resume_evidence_refs", item.get("evidence_refs", []))
            facts[item["id"]] = fact
        return {"facts": facts, "parser": result["parser"],
                "usage": result.get("model_usage", {}), "request_id": result.get("model_request_id")}

    @staticmethod
    def refresh_state(state):
        if not state["criteria_confirmed"]:
            state["workflow_state"] = "AWAITING_CRITERIA_CONFIRMATION"
            return
        active = [c["state"] for c in state["candidates"] if c["state"] != "COMPLETE"]
        state["workflow_state"] = "COMPLETE" if not active else (active[0] if len(set(active)) == 1 else "AWAITING_CANDIDATE_ACTIONS")

    def screen(self, state, candidate):
        candidate["state"] = "SCREENING"
        if candidate["round"] and "evaluation" in candidate:
            result = evaluate_profile(self.saved_profile(candidate["evaluation"]),
                                      state["job"]["criteria"], candidate["answers"],
                                      candidate["round"], candidate["id"], state["job"]["criteria_version"])
        else:
            result = evaluate(candidate["text"], state["job"]["criteria"], candidate["answers"],
                              self.resume_parser, candidate["round"], candidate["id"],
                              state["job"]["criteria_version"])
        candidate["evaluation"] = result; candidate["action"] = result["action"]; candidate["state"] = ACTION_STATE[result["action"]]; candidate["decision"] = None
        self.event(state, "RE_EVALUATE" if candidate["round"] else "SCREEN", candidate["id"], "Evidence evaluated against confirmed criteria.")
        self.event(state, result["action"], candidate["id"], result["recommendation"])

    def update(self, run_id, operation, payload):
        state = self.get(run_id)
        if operation == "confirm":
            if state["criteria_confirmed"]: raise ValueError('Criteria already confirmed. Create a new run to change the JD.')
            if not state["job"]["criteria"]: raise ValueError('No supported skills found. Add explicit skills to the JD.')
            state["criteria_confirmed"] = True; state["workflow_state"] = "SCREENING"
            self.event(state, "CRITERIA_CONFIRMED", None, "Recruiter confirmed extracted criteria.")
            for candidate in state["candidates"]: self.screen(state, candidate)
            self.rerank(state)
        else:
            if not state["criteria_confirmed"]: raise ValueError('Confirm criteria first.')
            candidate = next((c for c in state["candidates"] if c["id"] == payload.get("candidate_id")), None)
            if candidate is None: raise ValueError('Unknown candidate.')
            if operation == "followup":
                if candidate["action"] != "REQUEST_INFO": raise ValueError('This candidate is not awaiting clarification.')
                answers = payload.get("answers")
                if not isinstance(answers, dict) or not answers: raise ValueError('Provide at least one answer.')
                allowed = {q["criterion_id"] for q in candidate["evaluation"]["questions"]}
                for key, answer in answers.items():
                    if key not in allowed or not isinstance(answer, dict): raise ValueError('Invalid answer criterion.')
                    if answer.get("status") not in ("evidenced", "not_met", "unknown"): raise ValueError('Answer status must be evidenced, not_met or unknown.')
                    lines(answer.get("evidence"))
                candidate["answers"].update(answers); candidate["round"] += 1
                self.event(state, "FOLLOWUP_RECORDED", candidate["id"], "Recruiter-recorded evidence for current unknown criteria.")
                self.screen(state, candidate); self.rerank(state)
            elif operation == "review":
                if candidate["state"] not in ("SHORTLIST_REVIEW", "LOW_MATCH_REVIEW", "HUMAN_REVIEW"): raise ValueError('This candidate is not awaiting human review.')
                if candidate["decision"] is not None: raise ValueError('Decision already recorded.')
                decision = payload.get("decision")
                if decision not in ("shortlist", "hold", "decline"): raise ValueError('Choose shortlist, hold or decline.')
                lines(payload.get("reason")); candidate["decision"] = {"decision": decision, "reason": payload["reason"]}; candidate["action"] = "COMPLETE"; candidate["state"] = "COMPLETE"
                self.event(state, "HUMAN_DECISION", candidate["id"], decision); self.rerank(state)
            else: raise ValueError('Unknown operation.')
        self.refresh_state(state)
        self.store.save(run_id, state); return state
