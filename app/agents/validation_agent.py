from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import structlog
from app.db.models import Article
from app.core.llm_client import LLMClient

logger = structlog.get_logger()

class ValidationAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMClient()

    async def run(self):
        logger.info("agent_start", agent="ValidationAgent")
        
        # We need topics covered by BOTH Gov and Independent sources to find conflicts
        # This is expensive. We will sample top 5 keywords from Gov articles and see if Indep covers them.
        
        # 1. Get Gov Articles
        gov_res = await self.db.execute(select(Article).where(Article.source_type == 'gov').limit(10))
        gov_arts = gov_res.scalars().all()
        
        # 2. Get Indep Articles
        ind_res = await self.db.execute(select(Article).where(Article.source_type == 'independent').limit(20))
        ind_arts = ind_res.scalars().all()
        
        if not gov_arts or not ind_arts:
            logger.info("validation_skip", reason="Insufficient cross-source data")
            return {"status": "skipped"}

        # Naive matching: Compare checking titles/topics (Using LLM for smart matching)
        discrepancies = []
        
        # Batch analysis for conflicts
        prompt = f"""
        Compare these GOVERNMENT articles with INDEPENDENT articles.
        Identify any specific factual discrepancies or significant tone contrast (e.g. Govt says "Success", Media says "Failure").
        
        Return ONLY valid conflicts in this format:
        CONFLICT: [Topic] | GOVT: [Claim] | INDEP: [Claim] | VERDICT: [Analysis]
        
        If no conflict, return "NO_CONFLICT".
        
        GOVERNMENT SOURCES:
        {self._fmt(gov_arts)}
        
        INDEPENDENT SOURCES:
        {self._fmt(ind_arts)}
        """
        
        try:
            response = await self.llm.generate(prompt, system_instruction="You are a strict fact-checker.")
            if "NO_CONFLICT" not in response:
                discrepancies.append(response)
        except Exception as e:
            logger.error("validation_failed", error=str(e))

        # We don't have a specific DB table for Conflicts in the initial plan (Narrative fits, or just log/Report)
        # I will return them to be included in the report generation phase dynamically or logged
        # Rule 1: No ambiguity - I will store them in a simple Global/Shared state or return them. 
        # Since Agents pipeline is sequential, I can return them.
        
        logger.info("agent_complete", agent="ValidationAgent", conflicts_found=len(discrepancies))
        return {"status": "success", "conflicts": discrepancies}

    def _fmt(self, articles):
        return "\n".join([f"- {a.title}: {a.content_clean[:50]}..." for a in articles])
