"""LiveKit voice agent adapter for Philippines Bancassurance."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool, inference

from darwix.q3.ph.flow import PHLeadFlow
from darwix.q3.ph.knowledge import PHKnowledgeBase

load_dotenv()

PH_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME_PH", "darwix-bancassurance-ph")

PH_INSTRUCTIONS = """
You are a warm, polite, and professional Bancassurance customer assistance and
lead qualification voice agent for Darwix ProtectPlus in the Philippines.

Begin by greeting the customer warmly in natural Taglish using respectful markers
('po' and 'opo'). Explain that this is an initial bancassurance referral call,
not a final policy contract.

Mirror the customer's language preference: if they speak pure English, respond
in English; if they speak Tagalog, respond in Tagalog; by default, use natural Taglish.

Progressively collect qualification details using record_lead_detail:
age, Philippine residency, valid government ID, partner bank account status,
and simplified medical declaration. Then assist with plan preferences
(sum assured tier and payment mode).

If get_lead_status reports a contradiction in customer details, politely clarify
with the customer and call resolve_conflict with the confirmed value.

For ANY factual question regarding the policy, coverage, riders, payment channels,
grace period, or objections, you MUST call search_bancassurance_knowledge before
answering. Use only its returned context and citations. If it reports unavailable
information, speak the returned localized fallback message naturally and offer
to connect them with a Financial Advisor. Never invent policy facts or guarantee yields.

If the customer is upset, reports a bereavement/emergency, or asks to speak with
a human advisor, call request_human_assistance. Do not promise that a human will
immediately call back; explain that the request has been routed to the branch advisor.

When qualification is complete and all mandatory details are verified, explain that
their information is ready for the branch Financial Advisor.
""".strip()


class PHBancassuranceAgent(Agent):
    """LiveKit wrapper around the tested PH domain flow and PH knowledge base."""

    def __init__(self, flow: PHLeadFlow, knowledge_base: PHKnowledgeBase) -> None:
        super().__init__(instructions=PH_INSTRUCTIONS)
        self.flow = flow
        self.knowledge_base = knowledge_base

    @function_tool()
    async def search_bancassurance_knowledge(
        self, context: RunContext, query: str, language: str = ""
    ) -> dict:
        """Search grounded bancassurance knowledge or return localized fallback."""
        target_lang = language or self.flow.state.language
        res = self.knowledge_base.search(query, language=target_lang)
        return {
            "available": res.available,
            "context": res.context,
            "citations": [c.__dict__ for c in res.citations],
            "language": res.language.value,
        }

    @function_tool()
    async def record_lead_detail(
        self, context: RunContext, field: str, value: str
    ) -> dict:
        """Record a customer detail and return qualification status."""
        return self.flow.record_detail(field, value)

    @function_tool()
    async def resolve_conflict(
        self, context: RunContext, field: str, confirmed_value: str
    ) -> dict:
        """Resolve a conflicting qualification detail with confirmed value."""
        return self.flow.resolve_conflict(field, confirmed_value)

    @function_tool()
    async def get_lead_status(self, context: RunContext) -> dict:
        """Check current lead qualification status and missing fields."""
        return self.flow.status()

    @function_tool()
    async def set_preferred_language(
        self, context: RunContext, language: str
    ) -> dict:
        """Set caller's preferred language register (en, taglish, fil)."""
        return self.flow.set_language(language)

    @function_tool()
    async def request_human_assistance(
        self, context: RunContext, reason: str, urgency: str = "normal"
    ) -> dict:
        """Record a structured local escalation event without false promises."""
        return self.flow.request_human_assistance(reason, urgency=urgency)


server = AgentServer()


@server.rtc_session(agent_name=PH_AGENT_NAME)
async def bancassurance_ph_session(ctx: agents.JobContext) -> None:
    """LiveKit session handler for the Philippines Bancassurance agent."""
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(model="google/gemma-4-31b-it"),
        tts=inference.TTS(model="inworld/inworld-tts-2", voice="Ashley"),
    )
    flow = PHLeadFlow()
    flow.begin()
    await session.start(
        room=ctx.room,
        agent=PHBancassuranceAgent(flow, PHKnowledgeBase()),
    )
    await session.generate_reply(
        instructions=(
            "Greet the customer warmly in Taglish ('Magandang araw po!'), "
            "introduce Darwix ProtectPlus bancassurance care, and ask for their age."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
