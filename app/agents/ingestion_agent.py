import feedparser
import hashlib
import yaml
import structlog
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import Article
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

class IngestionAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_deterministic_id(self, url: str) -> str:
        # Rule 5: Deterministic ID based on URL (assumed unique per article)
        # Using URL instead of content for ID to prevent re-ingestion of same link
        return hashlib.sha256(url.encode()).hexdigest()

    async def run(self):
        logger.info("agent_start", agent="IngestionAgent")
        
        # Load sources from YAML
        try:
            with open(settings.SOURCES_PATH, 'r') as f:
                sources = yaml.safe_load(f)
        except Exception as e:
            logger.error("sources_load_failed", path=settings.SOURCES_PATH, error=str(e))
            raise e # Rule 9: Force clarity, don't guess.

        ingested_count = 0
        
        # Process English
        for url in sources.get('english', []):
            ingested_count += await self._process_feed(url, 'en')
            
        # Process Telugu
        for url in sources.get('telugu', []):
            ingested_count += await self._process_feed(url, 'te')

        logger.info("agent_complete", agent="IngestionAgent", new_articles=ingested_count)
        return {"status": "success", "ingested": ingested_count}

    async def _process_feed(self, feed_url: str, language: str) -> int:
        feed = feedparser.parse(feed_url)
        if hasattr(feed, 'bozo_exception') and feed.bozo_exception:
            logger.warning("feed_parse_error", url=feed_url, error=str(feed.bozo_exception))
            return 0

        count = 0
        for entry in feed.entries:
            try:
                # Rule 9: Force Clarity - ensure critical fields exist
                if not hasattr(entry, 'link') or not hasattr(entry, 'title'):
                    logger.warning("missing_fields", url=feed_url, entry=str(entry)[:50])
                    continue

                article_id = self._generate_deterministic_id(entry.link)
                
                # Check for duplication (Rule 2: No shortcuts - check DB)
                existing = await self.db.get(Article, article_id)
                if existing:
                    continue

                # Rule 7: Store raw first
                content = ""
                if hasattr(entry, 'content'):
                    content = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    content = entry.summary
                else:
                    # Some RSS feeds only have title/link. Store what we have.
                    content = entry.title

                # Determine correct pub_date
                pub_date = datetime.utcnow()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                     pub_date = datetime(*entry.published_parsed[:6])

                source_name = feed_url.split('/')[2] # naive domain extr
                source_type = "gov" if "pib.gov" in feed_url or "nic.in" in feed_url else "independent"

                new_article = Article(
                    id=article_id,
                    title=entry.title,
                    url=entry.link,
                    content_raw=content,
                    source=source_name,
                    source_type=source_type,
                    language=language,
                    pub_date=pub_date
                )
                self.db.add(new_article)
                count += 1
                
            except Exception as e:
                logger.error("article_ingest_failed", url=feed_url, error=str(e))
                # Rule 11: Reject mediocrity - fail this item but continue report? 
                # "Skip only that piece, never the entire report"
                continue
        
        await self.db.commit()
        return count
