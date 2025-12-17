from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import structlog
from app.db.models import Narrative
from app.core.llm_client import LLMClient

logger = structlog.get_logger()

class IdeaGeneratorAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMClient()

    async def run(self):
        logger.info("agent_start", agent="IdeaGeneratorAgent")
        
        # Get recent narratives
        res = await self.db.execute(select(Narrative).order_by(Narrative.created_at.desc()).limit(10))
        narratives = res.scalars().all()
        
        if not narratives:
             return {"status": "skipped", "reason": "No narratives"}

        narrative_text = "\n".join([f"Domain: {n.domain}\nNarrative: {n.narrative_text}" for n in narratives])

        prompt = f"""
        Based on these India-specific narratives, generate 10 RUTHLESSLY ACTIONABLE business or technical ideas.
        
        Rules:
        1. No generic "Start an AI company". Be specific: "Build a compliance tool for <Specific Act>".
        2. Must be derived from the provided text.
        3. Format: 
           1. **<Title>** | *Opportunity:* <Context> | *Idea:* <Solution>
        
        NARRATIVES:
        {narrative_text}
        """
        
        try:
            ideas = await self.llm.generate(prompt, system_instruction="You are a venture capitalist.")
            # Store ideas... where?
            # The user requirement asked for report inclusion.
            # I will return this data to be aggregated by ReportAgent or store in last narrative?
            # Creating a transient storage or just returning is fine for the pipeline script.
            return {"status": "success", "ideas": ideas}
        except Exception as e:
            logger.error("idea_gen_failed", error=str(e))
            return {"status": "error", "error": str(e)}
