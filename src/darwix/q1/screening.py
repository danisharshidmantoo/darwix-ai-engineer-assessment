"""Deterministic candidate-screening state and flow for Q1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ScreeningStage(str, Enum):
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    TECHNICAL_SIGNAL = "technical_signal"
    READY_FOR_REVIEW = "ready_for_review"
    ESCALATED = "escalated"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    INCOMPLETE = "incomplete"
    CONFLICTING = "conflicting"
    READY_FOR_HUMAN_REVIEW = "ready_for_human_review"


QUALIFICATION_FIELDS = (
    "enrollment_status",
    "work_authorization",
    "weekly_hours",
)
SCREENING_FIELDS = QUALIFICATION_FIELDS + (
    "availability_start_date",
    "python_experience",
    "rag_vector_experience",
)
MIN_TECHNICAL_SIGNAL_ANSWERS = 2
MIN_WEEKLY_HOURS = 20.0


@dataclass(frozen=True)
class Conflict:
    field: str
    first_value: str
    new_value: str


@dataclass(frozen=True)
class EscalationEvent:
    reason: str
    stage: ScreeningStage


@dataclass(frozen=True)
class ScreeningEvaluation:
    status: EligibilityStatus
    is_eligible: bool
    hard_requirement_violations: List[str]
    missing_fields: List[str]
    conflicts: List[Conflict]
    field_evaluations: Dict[str, str]


@dataclass
class CandidateScreeningState:
    """Explicit state collected during a screening conversation.

    This tracks information only. It deliberately does not determine a final
    hiring decision or approve policy exceptions.
    """

    stage: ScreeningStage = ScreeningStage.GREETING
    answers: Dict[str, str] = field(default_factory=dict)
    technical_signal_answers: List[str] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    escalation_requested: bool = False
    escalations: List[EscalationEvent] = field(default_factory=list)

    @property
    def missing_information(self) -> List[str]:
        missing = [f for f in SCREENING_FIELDS if f not in self.answers]
        if len(self.technical_signal_answers) < MIN_TECHNICAL_SIGNAL_ANSWERS:
            missing.append("role_relevant_questions")
        return missing

    @property
    def is_ready_for_human_review(self) -> bool:
        eval_res = evaluate_screening_state(self)
        return eval_res.status == EligibilityStatus.READY_FOR_HUMAN_REVIEW


class ScreeningFlow:
    """Shared state operations for LiveKit tools and deterministic simulations."""

    def __init__(self, state: CandidateScreeningState | None = None) -> None:
        self.state = state or CandidateScreeningState()

    def begin(self) -> CandidateScreeningState:
        if self.state.stage == ScreeningStage.GREETING:
            self.state.stage = ScreeningStage.QUALIFICATION
        return self.state

    def record_detail(self, field: str, value: str) -> dict:
        """Store one stated detail, retaining a conflict for clarification."""
        normalized_field = _normalize_screening_field(field)
        normalized_value = value.strip()
        if normalized_field not in SCREENING_FIELDS:
            raise ValueError(f"Unknown screening field: {field!r}")
        if not normalized_value:
            raise ValueError("Candidate detail cannot be empty")

        existing = self.state.answers.get(normalized_field)
        if existing is not None and _canonical(existing) != _canonical(normalized_value):
            conflict = Conflict(normalized_field, existing, normalized_value)
            if conflict not in self.state.conflicts:
                self.state.conflicts.append(conflict)
            return self.status()

        self.state.answers[normalized_field] = normalized_value
        self._advance_stage()
        return self.status()

    def record_technical_signal(self, answer: str) -> dict:
        normalized_answer = answer.strip()
        if not normalized_answer:
            raise ValueError("Technical-signal answer cannot be empty")
        if normalized_answer not in self.state.technical_signal_answers:
            self.state.technical_signal_answers.append(normalized_answer)
        self._advance_stage()
        return self.status()

    def resolve_conflict(self, field: str, confirmed_value: str) -> dict:
        """Clear the conflict on a field and update its confirmed value."""
        normalized_field = _normalize_screening_field(field)
        normalized_value = confirmed_value.strip()
        if normalized_field not in SCREENING_FIELDS:
            raise ValueError(f"Unknown screening field: {field!r}")
        if not normalized_value:
            raise ValueError("Confirmed value cannot be empty")

        self.state.answers[normalized_field] = normalized_value
        self.state.conflicts = [
            c for c in self.state.conflicts if c.field != normalized_field
        ]
        self._advance_stage()
        return self.status()

    def request_human_assistance(self, reason: str) -> dict:
        normalized_reason = reason.strip() or "Candidate requested human assistance"
        self.state.escalation_requested = True
        self.state.escalations.append(
            EscalationEvent(reason=normalized_reason, stage=self.state.stage)
        )
        self.state.stage = ScreeningStage.ESCALATED
        return self.status()

    def evaluate(self) -> ScreeningEvaluation:
        """Run deterministic policy evaluation on current state."""
        return evaluate_screening_state(self.state)

    def status(self) -> dict:
        evaluation = self.evaluate()
        return {
            "stage": self.state.stage.value,
            "eligibility_status": evaluation.status.value,
            "is_eligible": evaluation.is_eligible,
            "hard_requirement_violations": evaluation.hard_requirement_violations,
            "field_evaluations": evaluation.field_evaluations,
            "answers": dict(self.state.answers),
            "technical_signal_answer_count": len(self.state.technical_signal_answers),
            "missing_information": self.state.missing_information,
            "conflicts": [conflict.__dict__ for conflict in self.state.conflicts],
            "escalation_requested": self.state.escalation_requested,
            "ready_for_human_review": evaluation.status == EligibilityStatus.READY_FOR_HUMAN_REVIEW,
        }

    def _advance_stage(self) -> None:
        if self.state.escalation_requested:
            return
        evaluation = self.evaluate()
        if any(f not in self.state.answers for f in QUALIFICATION_FIELDS):
            self.state.stage = ScreeningStage.QUALIFICATION
        elif len(self.state.technical_signal_answers) < MIN_TECHNICAL_SIGNAL_ANSWERS:
            self.state.stage = ScreeningStage.TECHNICAL_SIGNAL
        elif evaluation.status == EligibilityStatus.READY_FOR_HUMAN_REVIEW:
            self.state.stage = ScreeningStage.READY_FOR_REVIEW


# --- Deterministic Policy Evaluation Helpers ---


def evaluate_screening_state(state: CandidateScreeningState) -> ScreeningEvaluation:
    """Evaluate candidate eligibility deterministically against Q2 policy."""
    violations: List[str] = []
    field_evals: Dict[str, str] = {}

    for field_name, answer in state.answers.items():
        is_valid, reason = _evaluate_field(field_name, answer)
        if not is_valid and reason:
            violations.append(reason)
            field_evals[field_name] = f"violated: {reason}"
        else:
            field_evals[field_name] = "satisfied"

    # Check for overall prior internships policy
    for answer in state.answers.values():
        if re.search(r"\b(2|two)\s+prior\s+internships?\b", answer, re.IGNORECASE) or re.search(
            r"\b(third|3rd)\s+internship\b", answer, re.IGNORECASE
        ):
            reason = (
                "Candidates who have completed two prior internships at the company "
                "under this program are not eligible per policy."
            )
            if reason not in violations:
                violations.append(reason)

    missing = state.missing_information
    conflicts = state.conflicts
    has_conflicts = bool(conflicts)
    is_eligible = len(violations) == 0

    if has_conflicts:
        status = EligibilityStatus.CONFLICTING
    elif not is_eligible:
        status = EligibilityStatus.INELIGIBLE
    elif not missing:
        status = EligibilityStatus.READY_FOR_HUMAN_REVIEW
    elif state.answers:
        status = EligibilityStatus.INCOMPLETE
    else:
        status = EligibilityStatus.INCOMPLETE

    return ScreeningEvaluation(
        status=status,
        is_eligible=is_eligible,
        hard_requirement_violations=violations,
        missing_fields=missing,
        conflicts=conflicts,
        field_evaluations=field_evals,
    )
def _normalize_screening_field(field: str) -> str:
    """Normalize natural-language field names to internal screening keys."""
    normalized = re.sub(r"[^a-z0-9]+", "_", field.strip().lower()).strip("_")

    aliases = {
        "enrollment_status": "enrollment_status",
        "enrollment": "enrollment_status",
        "work_authorization": "work_authorization",
        "work_authorisation": "work_authorization",
        "work_auth": "work_authorization",
        "weekly_availability": "weekly_hours",
        "weekly_hours": "weekly_hours",
        "hours_per_week": "weekly_hours",
        "availability_start_date": "availability_start_date",
        "start_date": "availability_start_date",
        "preferred_start_date": "availability_start_date",
        "python_experience": "python_experience",
        "python": "python_experience",
        "rag_vector_experience": "rag_vector_experience",
        "rag_experience": "rag_vector_experience",
        "vector_database_experience": "rag_vector_experience",
        "vector_db_experience": "rag_vector_experience",
    }

    if normalized not in aliases:
        raise ValueError(f"Unknown screening field: {field!r}")

    return aliases[normalized]

def _evaluate_field(field: str, value: str) -> Tuple[bool, Optional[str]]:
    """Check a single screening field against synthetic policy rules."""
    text = value.strip().lower()

    if field == "weekly_hours":
        # Policy: Must commit at least 20 hours per week
        # Extract numeric hours if present
        hours_match = re.search(r"(\d+(?:\.\d+)?)", text)
        if hours_match:
            hours = float(hours_match.group(1))
            if hours < MIN_WEEKLY_HOURS:
                return (
                    False,
                    f"Candidate committed {hours:g} hours per week, which violates the minimum "
                    f"{int(MIN_WEEKLY_HOURS)} hours per week requirement.",
                )
            return (True, None)

        if any(neg in text for neg in ["cannot do 20", "less than 20", "under 20", "only 10", "only 15"]):
            return (
                False,
                f"Candidate cannot commit to the minimum {int(MIN_WEEKLY_HOURS)} hours per week requirement.",
            )

        if "full-time" in text or "full time" in text:
            return (True, None)

        return (True, None)

    if field == "work_authorization":
        # Policy: Must be legally authorized to work or eligible under student authorization scheme
        # Check negative phrases first
        unauthorized_patterns = [
            r"\bnot\s+authorized\b",
            r"\bno\s+work\s+authorization\b",
            r"\bdo\s+not\s+have\s+(?:work\s+)?authorization\b",
            r"\bdon\'t\s+have\s+(?:work\s+)?authorization\b",
            r"\black\s+(?:work\s+)?authorization\b",
            r"\bunauthorized\b",
            r"\bcannot\s+legally\s+work\b",
            r"\bcan\'t\s+(?:legally\s+)?work\b",
            r"\bno\s+permit\b",
            r"\bineligible\s+to\s+work\b",
            r"\bno\s+visa\b",
            r"^no$",
            r"^no\b",
        ]
        if any(re.search(pat, text) for pat in unauthorized_patterns):
            # Guard against "no sponsorship needed"
            if "no sponsorship needed" not in text and "no sponsor required" not in text:
                return (
                    False,
                    "Candidate lacks required legal work authorization in the internship location.",
                )

        return (True, None)

    if field == "enrollment_status":
        # Policy: Enrolled in, or graduated within last 12 months from undergrad/grad program
        # Ineligible indicators: graduated >12 months ago, not enrolled/no degree
        ineligible_patterns = [
            r"\bgraduated\s+(\d+)\s+years?\s+ago\b",
            r"\bgraduated\s+(?:in\s+)?(20[01]\d|202[0-4])\b",  # Graduated before 2025
            r"\bgraduated\s+(\d+)\s+months?\s+ago\b",
            r"\bnot\s+enrolled\s+and\s+not\s+(?:a\s+)?graduate\b",
            r"\bnever\s+(?:attended|enrolled|went)\b",
            r"\bhigh\s+school\s+only\b",
        ]
        for pat in ineligible_patterns:
            m = re.search(pat, text)
            if m:
                if "months" in pat:
                    months = int(m.group(1))
                    if months > 12:
                        return (
                            False,
                            f"Candidate graduated {months} months ago (>12 months limit).",
                        )
                elif "years" in pat:
                    years = int(m.group(1))
                    if years >= 1:
                        return (
                            False,
                            f"Candidate graduated {years} years ago (>12 months limit).",
                        )
                else:
                    return (
                        False,
                        "Candidate must be enrolled in or have graduated within the last 12 months from an undergraduate or graduate program.",
                    )

        return (True, None)

    if field == "python_experience":
        # Job description: Working proficiency in Python is required
        no_python_patterns = [
            r"\bno\s+python\b",
            r"\bnever\s+used\s+python\b",
            r"\bdon\'t\s+know\s+python\b",
            r"\bdo\s+not\s+know\s+python\b",
            r"\bzero\s+python\b",
            r"\bno\s+experience\s+with\s+python\b",
            r"^none$",
            r"^no$",
        ]
        if any(re.search(pat, text) for pat in no_python_patterns):
            return (
                False,
                "Working proficiency in Python is a required qualification for this role.",
            )
        return (True, None)

    if field == "rag_vector_experience":
        # Preferred qualification, not hard disqualifier
        return (True, None)

    if field == "availability_start_date":
        return (True, None)

    return (True, None)


def _canonical(value: str) -> str:
    return " ".join(value.casefold().split())
