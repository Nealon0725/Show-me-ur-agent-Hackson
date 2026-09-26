"""Server-owned role criteria; no prepared evaluation is passed to the agent."""
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).resolve().parents[1] / 'data/clearhire_catalog.json').read_text(encoding='utf-8'))


def get_job(job_id):
    job = next((j for j in CATALOG['jobs'] if j['job_id'] == job_id), None)
    if job is None:
        raise ValueError('Unknown job.')
    return job


def agent_job(job_id):
    job = get_job(job_id)
    criteria = [{'id': key, 'label': job['criterion_titles'][i], 'description': description,
                 'source': description, 'required': True, 'weight': 0 if i == 0 else 2,
                 'scored': i != 0, 'type': 'role_requirement', 'role_id': job_id}
                for i, (key, description) in enumerate(job['criteria'])]
    return {'role': job['title'], 'criteria': criteria, 'raw_text': job['purpose'],
            'human_review_items': [], 'criteria_version': 1}
