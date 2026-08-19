"""Deterministic Q1 scenarios using the same domain services as LiveKit."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from darwix.q1.knowledge import KnowledgeBase
from darwix.q1.screening import ScreeningFlow


@dataclass(frozen=True)
class SimulationResult:
    name: str
    transcript: List[str]
    status: dict


def run_scenarios(knowledge_base: KnowledgeBase) -> Dict[str, SimulationResult]:
    """Run required assessment scenarios without LiveKit or model credentials."""
    return {
        "cooperative": _cooperative(knowledge_base),
        "objection": _objection(knowledge_base),
        "incomplete": _incomplete(knowledge_base),
        "conflicting": _conflicting(knowledge_base),
        "out_of_scope": _out_of_scope(knowledge_base),
        "human_assistance": _human_assistance(knowledge_base),
    }


def _cooperative(knowledge_base: KnowledgeBase) -> SimulationResult:
    flow = ScreeningFlow()
    flow.begin()
    transcript = [
        "Agent: Hello! Welcome to the screening call for the AI Engineer Intern role. This is an initial screening to confirm eligibility and background, not a final hiring decision. What is your current enrollment status?",
        "Candidate: Currently enrolled in a Computer Science degree.",
    ]
    flow.record_detail("enrollment_status", "Currently enrolled in a Computer Science degree")

    transcript.extend([
        "Agent: Are you legally authorized to work in the country where the internship is located?",
        "Candidate: Authorized to work where the internship is based.",
    ])
    flow.record_detail("work_authorization", "Authorized to work where the internship is based")

    transcript.extend([
        "Agent: Can you commit to at least 20 hours per week for the duration of the internship?",
        "Candidate: Yes, 20 hours per week.",
    ])
    flow.record_detail("weekly_hours", "20 hours per week")

    transcript.extend([
        "Agent: What is your earliest available start date?",
        "Candidate: June 2026.",
    ])
    flow.record_detail("availability_start_date", "June 2026")

    transcript.extend([
        "Agent: Could you describe your experience with Python?",
        "Candidate: I use Python for coursework and projects.",
    ])
    flow.record_detail("python_experience", "I use Python for coursework")

    transcript.extend([
        "Agent: Have you worked with RAG pipelines or vector databases?",
        "Candidate: I have introductory RAG experience.",
    ])
    flow.record_detail("rag_vector_experience", "I have introductory RAG experience")

    transcript.extend([
        "Agent: Technical question 1: How would you evaluate a retrieval pipeline against benchmarks?",
        "Candidate: I would test retrieval against labeled examples.",
    ])
    flow.record_technical_signal("I would test retrieval against labeled examples.")

    transcript.extend([
        "Agent: Technical question 2: How would you diagnose low similarity scores on relevant documents?",
        "Candidate: I would inspect failed retrieval results before changing a pipeline.",
    ])
    flow.record_technical_signal("I would inspect failed retrieval results before changing a pipeline.")

    transcript.append(
        "Agent: Thank you for sharing all the details. All required screening information has been collected and is ready for human review."
    )
    return _result("cooperative", transcript, flow)


def _objection(knowledge_base: KnowledgeBase) -> SimulationResult:
    flow = ScreeningFlow()
    flow.begin()
    query = "I don't have a vector database on my resume, am I still eligible?"
    transcript = [
        "Agent: What is your experience with RAG or vector databases?",
        f"Candidate: {query}",
    ]
    response = knowledge_base.search(query)
    transcript.append(f"Agent [retrieved from Q2]: {response.context}")
    return _result("objection", transcript, flow)


def _incomplete(knowledge_base: KnowledgeBase) -> SimulationResult:
    flow = ScreeningFlow()
    flow.begin()
    transcript = [
        "Agent: Hello! What is your current enrollment status?",
        "Candidate: Currently enrolled.",
    ]
    flow.record_detail("enrollment_status", "Currently enrolled")
    transcript.append(
        "Agent: Candidate stopped responding; remaining qualification and screening details are incomplete."
    )
    return _result("incomplete", transcript, flow)


def _conflicting(knowledge_base: KnowledgeBase) -> SimulationResult:
    flow = ScreeningFlow()
    flow.begin()
    transcript = [
        "Agent: How many hours per week can you commit to the internship?",
        "Candidate: 20 hours per week.",
    ]
    flow.record_detail("weekly_hours", "20 hours per week")

    transcript.extend([
        "Candidate: Actually, wait, during exams I might only do 10 hours per week.",
    ])
    flow.record_detail("weekly_hours", "10 hours per week")

    transcript.extend([
        "Agent: I noticed a conflict in your weekly availability (20 hours vs 10 hours). Could you confirm your commitment?",
        "Candidate: I can commit 20 hours per week full duration.",
    ])
    flow.resolve_conflict("weekly_hours", "20 hours per week")
    transcript.append("Agent: Conflict resolved with confirmed 20 hours per week.")
    return _result("conflicting", transcript, flow)


def _out_of_scope(knowledge_base: KnowledgeBase) -> SimulationResult:
    query = "Will it rain in Mumbai tomorrow?"
    transcript = [
        f"Candidate: {query}",
    ]
    response = knowledge_base.search(query)
    transcript.append(f"Agent: {response.context}")
    return _result("out_of_scope", transcript, ScreeningFlow())


def _human_assistance(knowledge_base: KnowledgeBase) -> SimulationResult:
    flow = ScreeningFlow()
    flow.begin()
    transcript = [
        "Candidate: I have a complex situation with my visa and want to speak with a recruiter directly.",
        "Agent: I understand. I am escalating this conversation for human assistance.",
    ]
    flow.request_human_assistance("Candidate asked to speak with a recruiter")
    return _result("human_assistance", transcript, flow)


def _result(name: str, transcript: List[str], flow: ScreeningFlow) -> SimulationResult:
    return SimulationResult(name=name, transcript=transcript, status=flow.status())


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic Q1 candidate-screening scenarios."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="Path to a pre-built Q2 JSON index (defaults to data/index/vector_store.json).",
    )
    args = parser.parse_args(argv)
    knowledge_base = (
        KnowledgeBase(index_path=args.index) if args.index else KnowledgeBase()
    )
    for name, result in run_scenarios(knowledge_base).items():
        print(f"[{name}]")
        for line in result.transcript:
            print(line)
        print(result.status)


if __name__ == "__main__":
    main()
