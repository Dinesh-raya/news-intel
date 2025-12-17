import asyncio
from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager
import structlog
from sqlalchemy.future import select

from app.config import get_settings
from app.db.session import init_db, get_db, AsyncSessionLocal
from app.db.models import Narrative

from app.agents.ingestion_agent import IngestionAgent
from app.agents.cleaning_agent import CleaningAgent
from app.agents.domain_agent import DomainAgent
from app.agents.narrative_agent import NarrativeAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.idea_generator_agent import IdeaGeneratorAgent
from app.agents.report_agent import ReportAgent

logger = structlog.get_logger()
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("startup", db_url_masked=settings.ASYNC_DATABASE_URL.split("@")[-1] if "@" in settings.ASYNC_DATABASE_URL else settings.ASYNC_DATABASE_URL)
    await init_db()
    yield
    # Shutdown

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "India Discourse Intelligence System Ready"}

@app.post("/api/v1/trigger-pipeline")
async def trigger_pipeline(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_full_pipeline)
    return {"status": "Pipeline triggered in background"}

async def run_full_pipeline():
    logger.info("pipeline_start")
    
    async with AsyncSessionLocal() as session:
        # 1. Ingestion
        ing_agent = IngestionAgent(session)
        ing_res = await ing_agent.run()
        
        # 2. Cleaning
        clean_agent = CleaningAgent(session)
        clean_res = await clean_agent.run()
        
        # 3. Domain Classification
        dom_agent = DomainAgent(session)
        dom_res = await dom_agent.run()
        
        # 4. Narrative Generation
        narr_agent = NarrativeAgent(session)
        narr_res = await narr_agent.run()
        
        # 5. Validation
        val_agent = ValidationAgent(session)
        val_res = await val_agent.run()
        
        # 6. Idea Generation
        idea_agent = IdeaGeneratorAgent(session)
        idea_res = await idea_agent.run()
        
        # Fetch Narratives for Report
        narratives_db = await session.execute(select(Narrative).order_by(Narrative.created_at.desc()).limit(20))
        narratives = narratives_db.scalars().all()
        
        # 7. Report
        rep_agent = ReportAgent()
        stats = {
            "ingested": ing_res.get('ingested'),
            "cleaned": clean_res.get('cleaned'),
            "classified": dom_res.get('classified')
        }
        await rep_agent.run(
            narratives=narratives,
            conflicts=val_res.get('conflicts', []),
            ideas=idea_res.get('ideas', "No ideas generated."),
            stats=stats
        )
        
    logger.info("pipeline_complete")

if __name__ == "__main__":
    # Local dev run
    asyncio.run(run_full_pipeline())
