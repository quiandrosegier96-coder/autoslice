"""
AutoSlice — Diagnostic data models for decision tracing.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleFiring:
    """One rule that fired during an engine run."""
    rule: str       # dot-separated path: e.g. "geometry.supports.type"
    trigger: str    # human-readable condition: e.g. "overhang_area_ratio=0.14 > 0.10"
    field: str      # PrintSettings field that changed
    before: Any     # value before this rule
    after: Any      # value after this rule


@dataclass
class DecisionTrace:
    """
    Full audit of one engine run.
    Passed through each pipeline pass; each pass appends RuleFiring entries.
    Only records when a value actually changes (before != after).
    """
    job_id: str
    printer_id: str
    filament: str
    nozzle_mm: float
    firings: list[RuleFiring] = field(default_factory=list)

    def record(self, rule: str, trigger: str, field: str, before: Any, after: Any) -> None:
        if before != after:
            self.firings.append(RuleFiring(rule, trigger, field, before, after))

    def to_list(self) -> list[dict]:
        return [
            {
                "rule": f.rule,
                "trigger": f.trigger,
                "field": f.field,
                "before": f.before,
                "after": f.after,
            }
            for f in self.firings
        ]
