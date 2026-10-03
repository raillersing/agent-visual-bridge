"""Manual pilot observations: comprehension cannot be inferred from clicks."""
from __future__ import annotations

from statistics import median

from .models import ValidationError, text
from .store import Store


def record_observation(service, review_id, observation):
    fields = {'participant', 'task', 'condition', 'active_seconds', 'interruptions',
              'understood_scope', 'constraints_lost', 'resume_attempts', 'resume_successes', 'effort'}
    if not isinstance(observation, dict) or set(observation) != fields:
        raise ValidationError('Pilot observation requires all documented fields')
    for key in ('participant', 'task'):
        text(observation[key], key, 200)
    if observation['task'] not in {'question', 'plan', 'correction'} or observation['condition'] not in {'terminal', 'bridge'}:
        raise ValidationError('Unknown pilot task or condition')
    for key in ('active_seconds', 'interruptions', 'constraints_lost', 'resume_attempts', 'resume_successes'):
        value = observation[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 10**9:
            raise ValidationError('Metrics must be finite non-negative numbers')
    if not isinstance(observation['understood_scope'], bool) or not 1 <= observation['effort'] <= 7:
        raise ValidationError('understood_scope must be boolean; effort is 1–7')
    if observation['resume_successes'] > observation['resume_attempts']:
        raise ValidationError('More successful resumes than attempts')
    service.get_review(review_id)
    with service.store.transaction() as db:
        Store.event(db, review_id, 'pilot_observation', observation)
    return observation


def pilot_report(service, review_id):
    records = [e for e in service.events(review_id) if e['kind'] == 'pilot_observation']
    result = {'review_id': review_id, 'status': 'no_observations' if not records else 'observations_available', 'conditions': {}}
    for condition in ('terminal', 'bridge'):
        rows = [r for r in records if r['condition'] == condition]
        if not rows:
            continue
        attempts = sum(r['resume_attempts'] for r in rows)
        result['conditions'][condition] = {
            'observations': len(rows), 'participants': len({r['participant'] for r in rows}),
            'tasks': sorted({r['task'] for r in rows}),
            'median_active_seconds': median(r['active_seconds'] for r in rows),
            'median_interruptions': median(r['interruptions'] for r in rows),
            'scope_comprehension_rate': sum(r['understood_scope'] for r in rows) / len(rows),
            'constraints_lost': sum(r['constraints_lost'] for r in rows),
            'resume_success_rate': sum(r['resume_successes'] for r in rows)/attempts if attempts else None,
            'median_effort': median(r['effort'] for r in rows)}
    result['comparable_tasks'] = sorted(set(result['conditions'].get('terminal', {}).get('tasks', [])) &
                                         set(result['conditions'].get('bridge', {}).get('tasks', [])))
    return result
