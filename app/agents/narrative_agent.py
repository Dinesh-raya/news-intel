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
                existing_res = await self.db.execute(select(Narrative).where(
                    Narrative.domain == domain,
                    Narrative.week_number == week_num,
                    Narrative.year == year
                ))
                existing = existing_res.scalar()
                
                # Rule 5: Determinism - but if existing is a failure placeholder, re-run
                if existing and existing.narrative_text != "No summary generated.":
                    continue

                # Get articles for this domain
                arts_res = await self.db.execute(select(Article).where(
                    Article.domain == domain,
                    Article.is_valid == True
                ).order_by(Article.pub_date.desc()).limit(20))
                
                articles = arts_res.scalars().all()
                if not articles:
                    continue

                # Generate Narrative
                narrative_text, sentiment = await self._generate_narrative(domain, articles)
                
                if existing:
                    existing.narrative_text = narrative_text
                    existing.sentiment = sentiment
                else:
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
        logger.info("agent_complete", agent="NarrativeAgent", processed=count)
        return {"status": "success", "narratives": count}

    async def _generate_narrative(self, domain: str, articles: list) -> tuple[str, str]:
        # Prepare data block
        snippets = []
        for a in articles:
            # Rule 6: Token efficiency - only clean text
            snippets.append(f"SOURCE:{a.source} | TITLE:{a.title} | CONTENT:{a.content_clean[:200]}")
        data_block = "\n".join(snippets)

        prompt = f"""
        Analyze the following articles for the Indian media domain '{domain}'.
        1. Write a strict, neutral, factual summary (max 3 sentences).
        2. Identify the overall sentiment: Optimistic, Pessimistic, Neutral, or Critical.
        
        CRITICAL: Your response must follow this EXACT format:
        SUMMARY: <your summary here>
        SENTIMENT: <the sentiment here>
        
        ARTICLES:
        {data_block}
        """

        response = await self.llm.generate(prompt, system_instruction="You are a senior neutral intelligence analyst specializing in Indian discourse.")
        
        # Robust parsing
        summary = "No summary generated."
        sentiment = "Neutral"
        
        for line in response.split('\n'):
            line = line.strip()
            if line.upper().startswith("SUMMARY"):
                summary = line.split(":", 1)[-1].strip() if ":" in line else line.replace("SUMMARY", "").strip()
            elif line.upper().startswith("SENTIMENT"):
                sentiment = line.split(":", 1)[-1].strip() if ":" in line else line.replace("SENTIMENT", "").strip()
        
        return summary, sentiment
