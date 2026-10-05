"""JSON subprocess engine, configured by the trusted host, never by a proposal."""
from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import tempfile
from pathlib import Path

from ..execution import ExecutionResult, UnknownExecution
from ..models import ValidationError, canonical


class JsonProcessExecutor:
    engine_id = 'json-process-v1'

    def __init__(self, argv, *, cwd, timeout=60, max_output=1024 * 1024):
        if (not isinstance(argv, (list, tuple)) or not argv
                or any(not isinstance(arg, str) or not arg or '\0' in arg for arg in argv)):
            raise ValidationError('Host must select a nonempty argument list')
        if (not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0
                or not isinstance(max_output, int) or isinstance(max_output, bool) or max_output <= 0):
            raise ValidationError('Timeout and output limit must be positive')
        self.argv, self.cwd = list(argv), str(Path(cwd).resolve())
        self.timeout, self.max_output = timeout, max_output

    def execute(self, request):
        # Temporary files bound memory usage even if a child produces noisy output.
        # stderr is intentionally not returned: provider logs can contain secrets.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            try:
                child = subprocess.Popen(self.argv, cwd=self.cwd, stdin=subprocess.PIPE,
                                         stdout=output, stderr=errors,
                                         start_new_session=os.name != 'nt')
            except OSError:
                return ExecutionResult(request.execution_id, 'failed', [], 'Engine could not start')
            try:
                child.communicate(canonical(request.document()).encode('utf-8'), timeout=self.timeout)
            except BaseException as exc:
                try:
                    if os.name != 'nt':
                        os.killpg(child.pid, signal.SIGKILL)
                    else:
                        child.kill()
                except ProcessLookupError:
                    pass
                child.wait()
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise UnknownExecution('Engine deadline exceeded; effects require reconciliation') from exc
                raise
            if child.returncode != 0:
                raise UnknownExecution('Engine exited without a confirmed result')
            output.seek(0)
            raw = output.read(self.max_output + 1)
            try:
                if len(raw) > self.max_output:
                    raise ValidationError('Engine output exceeded limit')
                return ExecutionResult.parse(json.loads(raw.decode('utf-8')), request)
            except (ValueError, UnicodeError, ValidationError) as exc:
                raise UnknownExecution('Engine returned an invalid or unbound result') from exc
