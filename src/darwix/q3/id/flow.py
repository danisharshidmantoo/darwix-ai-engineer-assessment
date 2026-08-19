"""Deterministic Indonesia Pembiayaan lead qualification and assistance flow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from darwix.q3.id.knowledge import LanguageRegister


class IDStage(str, Enum):
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


# Screening fields derived from the Indonesia corpus
MANDATORY_QUALIFICATION_FIELDS = (
    "age",
    "residency",
    "identity_document",
    "income",
    "bank_account_holder",
)
PLAN_FIELDS = (
    "dp",
    "tenor",
    "preferred_payment_mode",
)
ALL_SCREENING_FIELDS = MANDATORY_QUALIFICATION_FIELDS + PLAN_FIELDS

MIN_ELIGIBLE_AGE = 21
MAX_ELIGIBLE_AGE = 65
MIN_INCOME_RP = 3000000  # Rp3,000,000


@dataclass(frozen=True)
class Conflict:
    field: str
    first_value: str
    new_value: str


@dataclass(frozen=True)
class IDEscalationEvent:
    reason: str
    preferred_language: str
    urgency: str
    stage: IDStage
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    disclaimer: str = (
        "Permintaan eskalasi dicatat untuk tinjauan agen manusia. Waktu tanggapan bergantung pada jam kerja; "
        "tidak ada jaminan panggilan keluar segera."
    )


@dataclass(frozen=True)
class IDEvaluationResult:
    status: QualificationStatus
    is_eligible: bool
    violations: List[str]
    missing_fields: List[str]
    conflicts: List[Conflict]
    field_evaluations: Dict[str, str]


@dataclass
class IDLeadState:
    stage: IDStage = IDStage.GREETING
    language: LanguageRegister = LanguageRegister.FORMAL
    details: Dict[str, str] = field(default_factory=dict)
    conflicts: List[Conflict] = field(default_factory=list)
    escalation_requested: bool = False
    escalations: List[IDEscalationEvent] = field(default_factory=list)

    @property
    def missing_mandatory_fields(self) -> List[str]:
        return [f for f in MANDATORY_QUALIFICATION_FIELDS if f not in self.details]

    @property
    def is_ready_for_advisor(self) -> bool:
        eval_res = evaluate_id_state(self)
        return eval_res.status == QualificationStatus.READY_FOR_ADVISOR


class IDLeadFlow:
    def __init__(self, state: Optional[IDLeadState] = None) -> None:
        self.state = state or IDLeadState()

    def begin(self) -> IDLeadState:
        if self.state.stage == IDStage.GREETING:
            self.state.stage = IDStage.QUALIFICATION
        return self.state

    def set_language(self, language: LanguageRegister | str) -> dict:
        if isinstance(language, LanguageRegister):
            self.state.language = language
        else:
            norm = str(language).strip().lower()
            if norm in ("colloquial", "col", "id-col", "informal"):
                self.state.language = LanguageRegister.COLLOQUIAL
            elif norm in ("mix", "mixed", "id-mix"):
                self.state.language = LanguageRegister.MIXED
            else:
                self.state.language = LanguageRegister.FORMAL
        return self.status()

    def record_detail(self, field: str, value: str) -> dict:
        normalized_field = field.strip().lower()
        normalized_value = value.strip()
        if normalized_field not in ALL_SCREENING_FIELDS:
            raise ValueError(f"Unknown pembiayaan field: {field!r}")
        if not normalized_value:
            raise ValueError("Pembiayaan detail cannot be empty")

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
        normalized_field = field.strip().lower()
        normalized_value = confirmed_value.strip()
        if normalized_field not in ALL_SCREENING_FIELDS:
            raise ValueError(f"Unknown pembiayaan field: {field!r}")
        if not normalized_value:
            raise ValueError("Confirmed value cannot be empty")

        self.state.details[normalized_field] = normalized_value
        self.state.conflicts = [c for c in self.state.conflicts if c.field != normalized_field]
        self._advance_stage()
        return self.status()

    def request_human_assistance(self, reason: str, urgency: UrgencyLevel | str = UrgencyLevel.NORMAL) -> dict:
        norm_reason = reason.strip() or "Nasabah meminta bantuan agen manusia"
        norm_urgency = urgency.value if isinstance(urgency, UrgencyLevel) else str(urgency).lower()
        self.state.escalation_requested = True
        self.state.escalations.append(
            IDEscalationEvent(
                reason=norm_reason,
                preferred_language=self.state.language.value,
                urgency=norm_urgency,
                stage=self.state.stage,
            )
        )
        self.state.stage = IDStage.ESCALATED
        return self.status()

    def evaluate(self) -> IDEvaluationResult:
        return evaluate_id_state(self.state)

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
            self.state.stage = IDStage.QUALIFICATION
        elif any(f not in self.state.details for f in PLAN_FIELDS):
            self.state.stage = IDStage.PLAN_SELECTION
        elif evaluation.status == QualificationStatus.READY_FOR_ADVISOR:
            self.state.stage = IDStage.READY_FOR_ADVISOR


# --- Deterministic Policy Evaluators ---


def evaluate_id_state(state: IDLeadState) -> IDEvaluationResult:
    violations: List[str] = []
    field_evals: Dict[str, str] = {}

    for field_name, value in state.details.items():
        is_valid, reason = _evaluate_id_field(field_name, value)
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
        status = QualificationStatus.READY_FOR_ADVISOR
    else:
        status = QualificationStatus.INCOMPLETE

    return IDEvaluationResult(
        status=status,
        is_eligible=is_eligible,
        violations=violations,
        missing_fields=missing,
        conflicts=conflicts,
        field_evaluations=field_evals,
    )


def _evaluate_id_field(field: str, value: str) -> Tuple[bool, Optional[str]]:
    text = value.strip().lower()

    if field == "age":
        m = re.search(r"\b(\d+)\b", text)
        if m:
            age = int(m.group(1))
            if age < MIN_ELIGIBLE_AGE:
                return (False, f"Usia pemohon {age}; minimum adalah {MIN_ELIGIBLE_AGE} tahun.")
            if age > MAX_ELIGIBLE_AGE:
                return (False, f"Usia pemohon {age}; maksimum adalah {MAX_ELIGIBLE_AGE} tahun untuk pengajuan baru.")
            return (True, None)
        if any(neg in text for neg in ["di bawah", "kurang dari", "minor", "under"]):
            return (False, f"Pemohon harus berusia minimal {MIN_ELIGIBLE_AGE} tahun.")
        return (True, None)

    if field == "residency":
        non_resident_patterns = [r"\bnon-resident\b", r"tidak tinggal di indonesia", r"tinggal di luar", r"luar negeri", r"^no$"]
        if any(re.search(p, text) for p in non_resident_patterns):
            return (False, "Pemohon harus berdomisili di Indonesia untuk program pembiayaan ini.")
        return (True, None)

    if field == "identity_document":
        no_id_patterns = [r"tidak ada ktp", r"tidak punya ktp", r"no id", r"^no$", r"^none$"]
        if any(re.search(p, text) for p in no_id_patterns):
            return (False, "Diperlukan dokumen identitas (KTP atau KITAS/KITAP) untuk verifikasi.")
        return (True, None)

    if field == "income":
        # Look for numbers in Rp or plain digits
        m = re.search(r"(\d+[\.,]?\d*)", text.replace('.', '').replace(',', ''))
        if m:
            try:
                amt = int(m.group(1))
            except Exception:
                amt = None
            if amt is not None and amt < MIN_INCOME_RP:
                return (False, f"Penghasilan terdeteksi Rp{amt}; minimum persyaratan adalah Rp{MIN_INCOME_RP}.")
            return (True, None)
        # keywords
        if any(k in text for k in ["penghasilan rendah", "tidak cukup", "gak cukup", "gak kuat"]):
            return (False, "Penghasilan dinyatakan tidak memenuhi threshold produk.")
        return (True, None)

    if field == "bank_account_holder":
        no_bank_patterns = [r"tidak punya rekening", r"bukan pemegang rekening", r"no bank", r"^no$"]
        if any(re.search(p, text) for p in no_bank_patterns):
            return (False, "Diperlukan rekening bank mitra atau rekening aktif untuk autodebit / pembayaran.")
        return (True, None)

    if field == "dp":
        # DP can be 0% or numeric
        if "0%" in text or "0" == text:
            return (True, None)
        m = re.search(r"(\d+)%", text)
        if m:
            pct = int(m.group(1))
            if pct < 0 or pct > 100:
                return (False, "Persentase DP tidak valid.")
            return (True, None)
        return (True, None)

    if field == "tenor":
        m = re.search(r"\b(3|6|12|24|36)\b", text)
        if m:
            return (True, None)
        if any(k in text for k in ["tenor panjang", "perpanjangan tenor", "panjang"]):
            return (True, None)
        return (False, "Tenor harus berupa opsi yang tersedia (3,6,12,24,36 bulan).")

    if field == "preferred_payment_mode":
        return (True, None)

    return (True, None)


def _canonical(value: str) -> str:
    return " ".join(value.casefold().split())
