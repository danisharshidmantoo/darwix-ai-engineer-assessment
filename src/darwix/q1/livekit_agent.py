"""LiveKit entrypoint for the Q1 candidate-screening voice agent.

Run after building the Q2 index and setting the LiveKit environment values:

    lk agent dev

This module is deliberately a thin adapter: all screening state and knowledge
grounding live in ``darwix.q1`` and are covered by offline tests.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool, inference

from darwix.q1.knowledge import KnowledgeBase
from darwix.q1.screening import ScreeningFlow

load_dotenv()

AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "darwix-candidate-screening")

INSTRUCTIONS = """
You are a concise, respectful candidate-screening voice agent for an AI
Engineer Intern role. Begin by explaining that this is an initial screening
conversation, not a final hiring decision.

Collect candidate details progressively using record_candidate_detail:
enrollment status, work-authorization status, weekly availability, preferred
start date, Python experience, and RAG or vector-database experience. Then
collect two role-relevant technical-signal answers with
record_technical_signal. Ask one clear question at a time, identify missing or
conflicting details from get_screening_status, and ask for clarification.

If get_screening_status or record_candidate_detail reports conflicting details,
ask the candidate for clarification and call resolve_conflict with the confirmed
field and value to clear the conflict.

Candidates may ask questions or raise objections at any time. For every
factual question about the role, eligibility, process, policy, or objection,
you MUST call search_candidate_knowledge before answering. Use only its
returned context and citations. If it reports unavailable information, state
that exact fallback naturally and offer human assistance. Never invent facts,
make a hiring decision, approve an exception, or promise an outcome.

If the candidate asks for a person, is upset, or needs help outside the
available information, call request_human_assistance. When all fields are
collected, all requirements are satisfied, and no conflict remains, explain that
the information is ready for human review; do not imply acceptance or rejection.
""".strip()


class CandidateScreeningAgent(Agent):
    """LiveKit wrapper around the tested Q1 flow and Q2 knowledge adapter."""

    def __init__(self, flow: ScreeningFlow, knowledge_base: KnowledgeBase) -> None:
        super().__init__(instructions=INSTRUCTIONS)
        self.flow = flow
        self.knowledge_base = knowledge_base

    @function_tool()
    async def search_candidate_knowledge(
        self, context: RunContext, query: str
    ) -> dict:
        """Look up grounded candidate information before answering a factual question."""
        return self.knowledge_base.search(query).to_tool_result()

    @function_tool()
    async def record_candidate_detail(
        self, context: RunContext, field: str, value: str
    ) -> dict:
        """Record a candidate-provided screening detail and return missing/conflicting fields."""
        return self.flow.record_detail(field, value)

    @function_tool()
    async def resolve_conflict(
        self, context: RunContext, field: str, confirmed_value: str
    ) -> dict:
        """Resolve a conflicting screening detail using the candidate's confirmed value."""
        return self.flow.resolve_conflict(field, confirmed_value)

    @function_tool()
    async def record_technical_signal(
        self, context: RunContext, answer: str
    ) -> dict:
        """Record one answer to a role-relevant technical-signal question."""
        return self.flow.record_technical_signal(answer)

    @function_tool()
    async def get_screening_status(self, context: RunContext) -> dict:
        """Check which required details are missing or need conflict resolution."""
        return self.flow.status()

    @function_tool()
    async def request_human_assistance(
        self, context: RunContext, reason: str
    ) -> dict:
        """Record a local escalation when the candidate requests human help."""
        return self.flow.request_human_assistance(reason)


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def candidate_screening_session(ctx: agents.JobContext) -> None:
    """Start the official LiveKit STT → LLM → TTS voice pipeline."""
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(model="google/gemma-4-31b-it"),
        tts=inference.TTS(model="inworld/inworld-tts-2", voice="Ashley"),
    )
    flow = ScreeningFlow()
    flow.begin()
    await session.start(
        room=ctx.room,
        agent=CandidateScreeningAgent(flow, KnowledgeBase()),
    )
    await session.generate_reply(
        instructions=(
            "Greet the candidate, explain this is an initial screening call, "
            "and ask for their enrollment status."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
