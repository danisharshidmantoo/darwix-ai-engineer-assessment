"""LiveKit voice agent adapter for Indonesia Pembiayaan (multifinance / consumer finance)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool, inference

from darwix.q3.id.flow import IDLeadFlow
from darwix.q3.id.knowledge import IDKnowledgeBase

load_dotenv()

ID_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME_ID", "darwix-pembiayaan-id")

ID_INSTRUCTIONS = """
You are a warm, professional Indonesia consumer-finance voice agent for Darwix
Pembiayaan Konsumer. Use formal Bahasa Indonesia by default, but mirror the
caller: if they speak colloquial Bahasa Indonesia use that register; if they
code-switch with English finance terms (DP, down payment, tenor, cicilan),
respect their register.

Collect qualification details deterministically using the domain tools: age,
residency, identity document (KTP/KITAS), income, and bank account holder
status. Then collect plan preferences (DP, tenor, payment mode) using the
record_lead_detail tool.

For ANY factual question about product terms, cicilan, tenor, DP, denda,
jatuh tempo, or payment options, you MUST call search_pembiayaan_knowledge and
use only its returned context and citations to answer. If the knowledge base
reports unavailable information, speak the returned localized fallback in the
customer's current register and offer to connect them to a human agent.
Never invent financing policy.

If get_lead_status indicates a conflict, politely clarify and call resolve_conflict
with the confirmed value. For direct human requests ("mau live agent"), call
request_human_assistance. Do not promise guaranteed callbacks; provide the
standard escalation disclaimer.
""".strip()


class IDPembiayaanAgent(Agent):
    """LiveKit wrapper around the Indonesia qualification flow and knowledge base."""

    def __init__(self, flow: IDLeadFlow, knowledge_base: IDKnowledgeBase) -> None:
        super().__init__(instructions=ID_INSTRUCTIONS)
        self.flow = flow
        self.knowledge_base = knowledge_base

    @function_tool()
    async def search_pembiayaan_knowledge(self, context: RunContext, query: str, language: str = "") -> dict:
        """Search grounded pembiayaan knowledge or return localized fallback."""
        target_lang = language or self.flow.state.language
        res = self.knowledge_base.search(query, language=target_lang)
        return {
            "available": res.available,
            "context": res.context,
            "citations": [c.__dict__ for c in res.citations],
            "language": res.language.value,
        }

    @function_tool()
    async def record_lead_detail(self, context: RunContext, field: str, value: str) -> dict:
        """Record a customer detail and return qualification status."""
        return self.flow.record_detail(field, value)

    @function_tool()
    async def resolve_conflict(self, context: RunContext, field: str, confirmed_value: str) -> dict:
        """Resolve a conflicting qualification detail with confirmed value."""
        return self.flow.resolve_conflict(field, confirmed_value)

    @function_tool()
    async def get_lead_status(self, context: RunContext) -> dict:
        """Check current lead qualification status and missing fields."""
        return self.flow.status()

    @function_tool()
    async def set_preferred_language(self, context: RunContext, language: str) -> dict:
        """Set caller's preferred language register (formal/colloquial/mixed)."""
        return self.flow.set_language(language)

    @function_tool()
    async def request_human_assistance(self, context: RunContext, reason: str, urgency: str = "normal") -> dict:
        """Record a structured local escalation event without false promises."""
        return self.flow.request_human_assistance(reason, urgency=urgency)


server = AgentServer()


@server.rtc_session(agent_name=ID_AGENT_NAME)
async def pembiayaan_id_session(ctx: agents.JobContext) -> None:
    """LiveKit session handler for the Indonesia Pembiayaan agent."""
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="id"),
        llm=inference.LLM(model="google/gemma-4-31b-it"),
        tts=inference.TTS(model="inworld/inworld-tts-2", voice="Ashley"),
    )
    flow = IDLeadFlow()
    flow.begin()
    await session.start(
        room=ctx.room,
        agent=IDPembiayaanAgent(flow, IDKnowledgeBase()),
    )
    await session.generate_reply(
        instructions=(
            "Mulai dengan salam sopan dalam Bahasa Indonesia, perkenalkan layanan pembiayaan, "
            "dan tanyakan usia pemohon."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
