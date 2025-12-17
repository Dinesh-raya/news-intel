from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import structlog
from datetime import datetime
from app.db.models import Article, Narrative
from app.core.llm_client import LLMClient

logger = structlog.get_logger()

class NarrativeAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMClient()

    async def run(self):
        logger.info("agent_start", agent="NarrativeAgent")
        
        # Helper: Get curret week/year
        dt = datetime.now()
        week_num = dt.isocalendar()[1]
        year = dt.year

        # Get unique domains
        domains_res = await self.db.execute(select(Article.domain).distinct().where(Article.domain != None))
        domains = domains_res.scalars().all()

        count = 0
        for domain in domains:
            try:
                # Check if narrative already exists for this week/domain
                # Rule 5: Determinism - don't regenerate if done
                existing = await self.db.execute(select(Narrative).where(
                    Narrative.domain == domain,
                    Narrative.week_number == week_num,
                    Narrative.year == year
                ))
                if existing.scalar():
                    continue

                # Get articles for this domain
                arts_res = await self.db.execute(select(Article).where(
                    Article.domain == domain,
                    Article.is_valid == True
                ).limit(20)) # Cap at 20 for token efficiency context window
                
                articles = arts_res.scalars().all()
                if not articles:
                    continue

                # Generate Narrative
                narrative_text, sentiment = await self._generate_narrative(domain, articles)
                
                new_narr = Narrative(
                    domain=domain,
                    week_number=week_num,
                    year=year,
                    narrative_text=narrative_text,
                    sentiment=sentiment
                )
                self.db.add(new_narr)
                count += 1
            except Exception as e:
                logger.error("narrative_gen_failed", domain=domain, error=str(e))
        
        await self.db.commit()
        logger.info("agent_complete", agent="NarrativeAgent", generated=count)
        return {"status": "success", "narratives": count}

    async def _generate_narrative(self, domain: str, articles: list) -> tuple[str, str]:
        # Rule 6: Token Optimizer - Use TOON-like formatting manually effectively here
        # or let the client handle it.
        
        # Prepare data snippet
        snippets = []
        for a in articles:
            snippets.append(f"- [{a.source_type}] {a.title}: {a.content_clean[:100]}...")
        data_block = "\n".join(snippets)

        prompt = f"""
        Analyze these articles for the domain '{domain}'.
        1. Write a strict, neutral, factual summary of the dominant narrative (max 3 sentences).
        2. Identify the overall sentiment (Optimistic, Pessimistic, Neutral, Critical).
        
        Format:
        SUMMARY: <text>
        SENTIMENT: <words>
        
        ARTICLES:
        {data_block}
        """

        response = await self.llm.generate(prompt, system_instruction="You are a neutral intelligence analyst.")
        
        # Parse output
        summary = "No summary generated."
        sentiment = "Neutral"
        
        for line in response.split('\n'):
            if line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("SENTIMENT:"):
                sentiment = line.replace("SENTIMENT:", "").strip()
        
        return summary, sentiment
