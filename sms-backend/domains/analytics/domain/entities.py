"""
Analytics Domain Entities — Phase 10 (Prompt 19)
Pure Python dataclasses. No Django. No ORM.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class DashboardMetric:
    """A single numeric KPI shown on a dashboard."""
    key: str
    label: str
    value: float
    unit: Optional[str] = None
    change_pct: Optional[float] = None
    color: Optional[str] = None


@dataclass
class Report:
    id: Optional[int]
    name: str
    report_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    generated_at: Optional[str] = None
    generated_by: Optional[int] = None
    result_url: Optional[str] = None

    REPORT_TYPES = ("ENROLLMENT", "ATTENDANCE", "FINANCE", "BEHAVIOR", "PERFORMANCE")

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Report name is required")
        if self.report_type not in self.REPORT_TYPES:
            raise ValueError(f"report_type must be one of {self.REPORT_TYPES}")
