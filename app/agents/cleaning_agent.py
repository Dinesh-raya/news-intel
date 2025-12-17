from bs4 import BeautifulSoup
from langdetect import detect, LangDetectException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import structlog
from app.db.models import Article

logger = structlog.get_logger()

class CleaningAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self):
        logger.info("agent_start", agent="CleaningAgent")
        
        # Fetch articles with no clean content
        result = await self.db.execute(select(Article).where(Article.content_clean == None))
        articles = result.scalars().all()
        
        cleaned_count = 0
        for article in articles:
            try:
                # 1. Clean HTML
                soup = BeautifulSoup(article.content_raw, 'html.parser')
                text = soup.get_text(separator=' ')
                
                # 2. Normalize whitespace
                text = " ".join(text.split())
                
                # 3. Verify language (optional double-check)
                # Rule 10: Interrogate the data
                try:
                    detected = detect(text) if len(text) > 50 else article.language
                except LangDetectException:
                    detected = article.language # fallback
                
                if detected != article.language and detected in ['en', 'te']:
                     logger.warning("language_mismatch", id=article.id, expected=article.language, found=detected)
                     # We might update the language, or flag it. For now, trusting source-declared language unless strongly opposed
                     # But adhering to "No ambiguity": if really unsure, we'd flag valid=False
                
                if len(text) < 20:
                     # Too short, mark invalid
                     article.is_valid = False
                     article.validation_error = "Content too short"
                else:
                    article.content_clean = text
                
                cleaned_count += 1
            except Exception as e:
                logger.error("cleaning_failed", id=article.id, error=str(e))
                article.is_valid = False
                article.validation_error = f"Cleaning failed: {str(e)}"
        
        await self.db.commit()
        logger.info("agent_complete", agent="CleaningAgent", processed=cleaned_count)
        return {"status": "success", "cleaned": cleaned_count}
