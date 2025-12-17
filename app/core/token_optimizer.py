import re
import json
import hashlib
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()

class TokenOptimizer:
    """
    Ruthlessly optimizes prompts to save tokens.
    Strategy:
    1. JSON -> TOON (Token Optimized Object Notation): Minify, remove obvious keys if positional is clear.
    2. Stop word removal for context (aggressive).
    3. Caching: MD5 hash of prompts to avoid re-calls (simulated here, typically would use DB/Redis).
    """
    
    def __init__(self):
        self._cache = {} # In-memory cache for the run
    
    def to_toon(self, data: Dict[str, Any]) -> str:
        """
        Converts detailed JSON to a minimal string representation.
        Example: {"title": "The Hindu", "date": "2025-10-10"} -> "The Hindu|2025-10-10"
        """
        # specialized logic for common structures
        if "articles" in data and isinstance(data["articles"], list):
            # Compact list of articles
            # Format: ID|TITLE|SOURCE
            lines = ["ID|TITLE|SOURCE|CONTENT_SNIPPET"]
            for art in data["articles"]:
                snippet = (art.get('content_clean') or art.get('content_raw') or "")[:150].replace('\n', ' ')
                lines.append(f"{art.get('id')}|{art.get('title')}|{art.get('source')}|{snippet}")
            return "\n".join(lines)
        
        # Default fallback: Minified JSON
        return json.dumps(data, separators=(',', ':'))

    def compress_text(self, text: str) -> str:
        """
        Normalizes whitespace. 
        Note: Removed stop-word removal as it was too destructive for news analysis.
        """
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def optimize_prompt_structure(self, system_prompt: str, user_data: Any) -> str:
        """
        Combines system prompt with TOON-formatted data.
        """
        data_str = self.to_toon(user_data)
        return f"{system_prompt}\n\nDATA:\n{data_str}"

    def report_savings(self, original_text: str, optimized_text: str):
        orig_len = len(original_text.split()) # Approx tokens
        opt_len = len(optimized_text.split())
        saved = max(0, orig_len - opt_len)
        logger.info("token_optimization", original=orig_len, optimized=opt_len, saved=saved)
        return saved
