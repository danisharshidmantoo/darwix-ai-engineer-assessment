"""Deterministic Philippines Bancassurance lead qualification and assistance flow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from darwix.q3.ph.knowledge import LanguageRegister


class BancassuranceStage(str, Enum):
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    PLAN_SELECTION = "plan_selection"
    READY_FOR_ADVISOR = "ready_for_advisor"
    ESCALATED = "escalated"


class QualificationStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    INCOMPLETE = "incomplete"
    CONFLICTING = "conflicting"
    READY_FOR_ADVISOR = "ready_for_advisor"


class UrgencyLevel(str, Enum):
    NORMAL = "normal"
    HIGH = "high"


MANDATORY_QUALIFICATION_FIELDS = (
    "age",
    "residency",
    "government_id",
    "bank_account_holder",
    "medical_declaration",
)
PLAN_FIELDS = (
    "sum_assured_tier",
    "preferred_payment_mode",
)
ALL_SCREENING_FIELDS = MANDATORY_QUALIFICATION_FIELDS + PLAN_FIELDS

MIN_ELIGIBLE_AGE = 18
MAX_ELIGIBLE_AGE = 60


@dataclass(frozen=True)
class Conflict:
    field: str
    first_value: str
    new_value: str


@dataclass(frozen=True)
class PHEscalationEvent:
    """Structured local escalation event without false promises of guaranteed callback."""

    reason: str
    preferred_language: str
    urgency: str
    stage: BancassuranceStage
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    disclaimer: str = (
        "Escalation request queued locally for licensed Financial Advisor "
        "review. Availability and response times depend on branch operating hours; "
        "no immediate outbound call is guaranteed."
    )


@dataclass(frozen=True)
class PHEvaluationResult:
    status: QualificationStatus
    is_eligible: bool
    violations: List[str]
    missing_fields: List[str]
    conflicts: List[Conflict]
    field_evaluations: Dict[str, str]


@dataclass
class PHLeadState:
    """Explicit state collected during a Bancassurance screening conversation."""

    stage: BancassuranceStage = BancassuranceStage.GREETING
    language: LanguageRegister = LanguageRegister.TAGLISH
    details: Dict[str, str] = field(default_factory=dict)
    conflicts: List[Conflict] = field(default_factory=list)
    escalation_requested: bool = False
    escalations: List[PHEscalationEvent] = field(default_factory=list)

    @property
    def missing_mandatory_fields(self) -> List[str]:
        return [f for f in MANDATORY_QUALIFICATION_FIELDS if f not in self.details]

    @property
    def is_ready_for_advisor(self) -> bool:
        eval_res = evaluate_ph_state(self)
        return eval_res.status == QualificationStatus.READY_FOR_ADVISOR


class PHLeadFlow:
    """Deterministic business logic for Philippines Bancassurance lead qualification."""

    def __init__(self, state: Optional[PHLeadState] = None) -> None:
        self.state = state or PHLeadState()

    def begin(self) -> PHLeadState:
        if self.state.stage == BancassuranceStage.GREETING:
            self.state.stage = BancassuranceStage.QUALIFICATION
        return self.state

    def set_language(self, language: LanguageRegister | str) -> dict:
        """Update current conversation language/register."""
        if isinstance(language, LanguageRegister):
            self.state.language = language
        else:
            norm = str(language).strip().lower()
            if norm in ("en", "english"):
                self.state.language = LanguageRegister.ENGLISH
            elif norm in ("fil", "filipino", "tl", "tagalog"):
                self.state.language = LanguageRegister.FILIPINO
            else:
                self.state.language = LanguageRegister.TAGLISH
        return self.status()

    def record_detail(self, field: str, value: str) -> dict:
        """Store a candidate/client stated detail, identifying any conflict."""
        normalized_field = field.strip().lower()
        normalized_value = value.strip()
        if normalized_field not in ALL_SCREENING_FIELDS:
            raise ValueError(f"Unknown bancassurance field: {field!r}")
        if not normalized_value:
            raise ValueError("Bancassurance detail cannot be empty")

        existing = self.state.details.get(normalized_field)
        if existing is not None and _canonical(existing) != _canonical(normalized_value):
            conflict = Conflict(normalized_field, existing, normalized_value)
            if conflict not in self.state.conflicts:
                self.state.conflicts.append(conflict)
            return self.status()

        self.state.details[normalized_field] = normalized_value
        self._advance_stage()
        return self.status()

    def resolve_conflict(self, field: str, confirmed_value: str) -> dict:
        """Clear conflict for a field and store confirmed value."""
        normalized_field = field.strip().lower()
        normalized_value = confirmed_value.strip()
        if normalized_field not in ALL_SCREENING_FIELDS:
            raise ValueError(f"Unknown bancassurance field: {field!r}")
        if not normalized_value:
            raise ValueError("Confirmed value cannot be empty")

        self.state.details[normalized_field] = normalized_value
        self.state.conflicts = [
            c for c in self.state.conflicts if c.field != normalized_field
        ]
        self._advance_stage()
        return self.status()

    def request_human_assistance(
        self, reason: str, urgency: UrgencyLevel | str = UrgencyLevel.NORMAL
    ) -> dict:
        """Record a structured local escalation event without false promises."""
        norm_reason = reason.strip() or "Customer requested human assistance"
        norm_urgency = (
            urgency.value if isinstance(urgency, UrgencyLevel) else str(urgency).lower()
        )
        self.state.escalation_requested = True
        self.state.escalations.append(
            PHEscalationEvent(
                reason=norm_reason,
                preferred_language=self.state.language.value,
                urgency=norm_urgency,
                stage=self.state.stage,
            )
        )
        self.state.stage = BancassuranceStage.ESCALATED
        return self.status()

    def evaluate(self) -> PHEvaluationResult:
        """Run deterministic policy evaluation against PH bancassurance rules."""
        return evaluate_ph_state(self.state)

    def status(self) -> dict:
        evaluation = self.evaluate()
        return {
            "stage": self.state.stage.value,
            "language": self.state.language.value,
            "qualification_status": evaluation.status.value,
            "is_eligible": evaluation.is_eligible,
            "hard_requirement_violations": evaluation.violations,
            "field_evaluations": evaluation.field_evaluations,
            "details": dict(self.state.details),
            "missing_mandatory_fields": self.state.missing_mandatory_fields,
            "conflicts": [conflict.__dict__ for conflict in self.state.conflicts],
            "escalation_requested": self.state.escalation_requested,
            "ready_for_advisor": evaluation.status == QualificationStatus.READY_FOR_ADVISOR,
        }

    def _advance_stage(self) -> None:
        if self.state.escalation_requested:
            return
        evaluation = self.evaluate()
        if any(f not in self.state.details for f in MANDATORY_QUALIFICATION_FIELDS):
            self.state.stage = BancassuranceStage.QUALIFICATION
        elif any(f not in self.state.details for f in PLAN_FIELDS):
            self.state.stage = BancassuranceStage.PLAN_SELECTION
        elif evaluation.status == QualificationStatus.READY_FOR_ADVISOR:
            self.state.stage = BancassuranceStage.READY_FOR_ADVISOR


# --- Deterministic Policy Evaluators ---


def evaluate_ph_state(state: PHLeadState) -> PHEvaluationResult:
    """Evaluate applicant details against the synthetic PH Bancassurance policy."""
    violations: List[str] = []
    field_evals: Dict[str, str] = {}

    for field_name, value in state.details.items():
        is_valid, reason = _evaluate_ph_field(field_name, value)
        if not is_valid and reason:
            violations.append(reason)
            field_evals[field_name] = f"violated: {reason}"
        else:
            field_evals[field_name] = "satisfied"

    missing = state.missing_mandatory_fields
    conflicts = state.conflicts
    has_conflicts = bool(conflicts)
    is_eligible = len(violations) == 0

    if has_conflicts:
        status = QualificationStatus.CONFLICTING
    elif not is_eligible:
        status = QualificationStatus.INELIGIBLE
    elif not missing:
        # All mandatory qualification fields satisfied
        status = QualificationStatus.READY_FOR_ADVISOR
    else:
        status = QualificationStatus.INCOMPLETE

    return PHEvaluationResult(
        status=status,
        is_eligible=is_eligible,
        violations=violations,
        missing_fields=missing,
        conflicts=conflicts,
        field_evaluations=field_evals,
    )


def _evaluate_ph_field(field: str, value: str) -> Tuple[bool, Optional[str]]:
    text = value.strip().lower()

    if field == "age":
        # Policy: 18 to 60 years old
        m = re.search(r"\b(\d+)\b", text)
        if m:
            age = int(m.group(1))
            if age < MIN_ELIGIBLE_AGE:
                return (
                    False,
                    f"Applicant is {age} years old; minimum eligible age is {MIN_ELIGIBLE_AGE}.",
                )
            if age > MAX_ELIGIBLE_AGE:
                return (
                    False,
                    f"Applicant is {age} years old; maximum eligible age for ProtectPlus is {MAX_ELIGIBLE_AGE}.",
                )
            return (True, None)
        if any(neg in text for neg in ["minor", "below 18", "under 18"]):
            return (False, f"Applicant must be at least {MIN_ELIGIBLE_AGE} years old.")
        if any(neg in text for neg in ["senior", "above 60", "over 60", "65", "70"]):
            return (
                False,
                f"Applicants over {MAX_ELIGIBLE_AGE} are not eligible for new ProtectPlus policies.",
            )
        return (True, None)

    if field == "residency":
        # Policy: Must reside in the Philippines
        non_resident_patterns = [
            r"\bnon-resident\b",
            r"\bnot\s+residing\s+in\s+(?:the\s+)?philippines\b",
            r"\bliving\s+(?:overseas|abroad|permanently)\b",
            r"\b(?:overseas|abroad|dubai|uae|singapore|usa|canada|australia|qatar|saudi|japan)\b",
            r"^no$",
        ]
        if any(re.search(p, text) for p in non_resident_patterns):
            return (
                False,
                "Must be residing in the Philippines to apply for standard bancassurance referral.",
            )
        return (True, None)

    if field == "government_id":
        # Policy: Must have valid Philippine government ID
        no_id_patterns = [
            r"\bno\s+valid\s+id\b",
            r"\bno\s+id\b",
            r"\bwalang\s+id\b",
            r"^none$",
            r"^no$",
            r"^wala$",
        ]
        if any(re.search(p, text) for p in no_id_patterns):
            return (
                False,
                "At least one valid Philippine government-issued ID is required for verification.",
            )
        return (True, None)

    if field == "bank_account_holder":
        # Policy: Must be account holder with partner bank for ADA
        no_bank_patterns = [
            r"\bno\s+bank\s+account\b",
            r"\bnot\s+an?\s+account\s+holder\b",
            r"\bwalang\s+account\b",
            r"^no$",
            r"^wala$",
        ]
        if any(re.search(p, text) for p in no_bank_patterns):
            return (
                False,
                "Active partner bank deposit account or credit card is required for bancassurance Auto-Debit Arrangement.",
            )
        return (True, None)

    if field == "medical_declaration":
        # Policy: Good health, no hospitalization >14 days or major surgery in last 12 months, no terminal illness/dialysis
        unhealthy_patterns = [
            r"\bterminal\b",
            r"\bdialysis\b",
            r"\bhospitalized\s+for\s+(?:more\s+than\s+14\s+days|1\s+month|30\s+days|3\s+weeks)\b",
            r"\brecent\s+major\s+surgery\b",
            r"\bactive\s+cancer\b",
            r"\bsevere\s+heart\s+attack\b",
            r"^failed$",
        ]
        if any(re.search(p, text) for p in unhealthy_patterns):
            return (
                False,
                "Applicant does not meet simplified health declaration guidelines.",
            )
        return (True, None)

    if field in ("sum_assured_tier", "preferred_payment_mode"):
        return (True, None)

    return (True, None)


def _canonical(value: str) -> str:
    return " ".join(value.casefold().split())
