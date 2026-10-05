"""Provider-neutral execution messages. Host configuration selects the engine."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .models import ValidationError, canonical


@dataclass(frozen=True)
class ExecutionRequest:
    execution_id: str
    review_id: str
    revision: int
    agent_id: str
    session_id: str
    fingerprint: str
    item: dict[str, Any]
    constraints: list[str]
    engine_id: str = "legacy-callback"
    authorization: dict[str, Any] = field(default_factory=dict)
    contract_version: int = 1

    def document(self):
        result = asdict(self)
        canonical(result)
        return result


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    state: str
    evidence: list
    message: str = ''

    @classmethod
    def parse(cls, value, request):
        if not isinstance(value, dict) or set(value) - {'execution_id', 'state', 'evidence', 'message'}:
            raise ValidationError('Invalid execution result fields')
        if value.get('execution_id') != request.execution_id:
            raise ValidationError('Execution identity mismatch')
        if value.get('state') not in {'succeeded', 'failed', 'unknown'}:
            raise ValidationError('Invalid execution result state')
        if not isinstance(value.get('evidence'), list) or not isinstance(value.get('message', ''), str) or len(value.get('message', '')) > 100000:
            raise ValidationError('Execution evidence must be a list and message must be text')
        canonical(value)
        return cls(value['execution_id'], value['state'], value['evidence'], value.get('message', ''))


class UnknownExecution(RuntimeError):
    """An action may have had effects; reconciliation is required before retry."""
