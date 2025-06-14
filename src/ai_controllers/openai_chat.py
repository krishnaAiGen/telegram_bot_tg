# src/ai_controllers/openai_chat.py
import aiohttp
from config import APP_CONFIG

API_KEY = APP_CONFIG.get("openai_api_key")
CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
MODERATION_API_URL = "https://api.openai.com/v1/moderations"

async def get_llm_response(content: str, model: str = "gpt-4", max_tokens: int = 300) -> str:
    """Gets a response from the OpenAI Chat Completion API asynchronously."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(CHAT_API_URL, headers=headers, json=payload, timeout=90) as response:
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Error calling OpenAI Chat API: {e}")
            return "Error: Could not get a response from the language model."

async def is_content_offensive(text_to_check: str) -> bool:
    """Checks text against OpenAI's Moderation API. Returns True if flagged."""
    if not text_to_check:
        return False
        
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {"input": text_to_check}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(MODERATION_API_URL, headers=headers, json=payload, timeout=10) as response:
                response.raise_for_status()
                result = await response.json()
                is_flagged = result["results"][0]["flagged"]
                
                if is_flagged:
                    print(f"GUARDRAIL: Content flagged as offensive. Text: '{text_to_check[:100]}...'")
                return is_flagged
        except Exception as e:
            # If the moderation check fails, we default to assuming the content is safe to avoid blocking the bot.
            print(f"Warning: Moderation API call failed: {e}. Assuming content is safe as a fallback.")
            return False