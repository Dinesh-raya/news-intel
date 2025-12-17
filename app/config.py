import os
import re
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "India Discourse Intelligence"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Text Generation / LLM
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    LLM_MODEL: str = "mistralai/mistral-7b-instruct"
    SITE_URL: str = os.getenv("SITE_URL", "http://localhost:8000")
    APP_NAME_HEADER: str = "India Discourse Intel"
    
    # Database (Supabase Postgres)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./india_intel.db")
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        # 1. Start with standard strip
        url = self.DATABASE_URL.strip()
        
        # 2. Ruthless ASCII-only filter (kills hidden non-breaking spaces \u00a0, zero-width spaces \u200b, etc.)
        url = "".join(c for c in url if 32 < ord(c) < 127)
        
        # Safe fallback if user pasted just the hostname (rare but possible)
        if not url.startswith(("postgresql://", "postgres://", "sqlite")):
             return url # Let SQLAlchemy handle the error naturally
             
        # 3. Ensure we use asyncpg
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
            
        return url
    
    # Supabase Storage (Cloud Native)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET: str = "reports"

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SOURCES_PATH: str = os.path.join(os.path.dirname(BASE_DIR), "sources", "rss_sources.yaml")
    REPORTS_DIR: str = os.path.join(os.path.dirname(BASE_DIR), "reports")

    # Rutheless Config
    STRICT_MODE: bool = True
    TOKEN_OPTIMIZER_ENABLED: bool = True
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
