import json
import aiohttp
import structlog
from app.config import get_settings
from app.core.token_optimizer import TokenOptimizer

logger = structlog.get_logger()
settings = get_settings()

class LLMClient:
    def __init__(self):
        self.optimizer = TokenOptimizer()
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.LLM_MODEL
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            logger.warning("OpenRouter API Key Missing. LLM calls will fail or mock.")

    async def generate(self, prompt: str, system_instruction: str = "") -> str:
        if not self.api_key:
            if settings.DEBUG:
                return "MOCK_LLM_OUTPUT (OpenRouter Missing): Actionable Idea generated."
            raise ValueError("OPENROUTER_API_KEY not set")

        # RUTHLESS IMPLEMENTATION:
        # 1. Compress Prompt (JSON -> TOON done by caller usually, but we ensure text compression here if needed)
        # 2. Deterministic Params
        
        full_prompt = f"{system_instruction}\n\n{prompt}"
        
        # Optimize context if large (naive approach for this snippet)
        if len(full_prompt) > 4000:
            full_prompt = self.optimizer.compress_text(full_prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": settings.SITE_URL,
            "X-Title": settings.APP_NAME_HEADER,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.0, # Deterministic
            "top_p": 0.9,
            "max_tokens": 1000 # Prevent runaways
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data['choices'][0]['message']['content']
                        # Report Savings (Mock comparison)
                        self.optimizer.report_savings(full_prompt, full_prompt) 
                        return content
                    else:
                        error_text = await resp.text()
                        logger.error("openrouter_error", status=resp.status, body=error_text)
                        raise Exception(f"OpenRouter API Error: {resp.status} - {error_text}")
                        
        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            raise e
