# src/services/openai_chat.py
import aiohttp
from config.settings import APP_CONFIG

# --- Module-level Constants for Security and Clarity ---
# The API key is sourced from the central config, which gets it from .env.
API_KEY = APP_CONFIG.get("openai_api_key")
CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
MODERATION_API_URL = "https://api.openai.com/v1/moderations"

async def get_llm_response(content: str, model: str = "gpt-4", max_tokens: int = 300) -> str:
    """
    Asynchronously gets a response from the OpenAI Chat Completion API.
    This is the application's "creative writer".
    """
    if not API_KEY:
        print("Error: OpenAI API key is not configured.")
        return "Error: Service not configured."

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens}
    
    # aiohttp.ClientSession is used for efficient, asynchronous HTTP requests.
    async with aiohttp.ClientSession() as session:
        try:
            # A timeout is crucial to prevent the application from hanging on a slow API response.
            async with session.post(CHAT_API_URL, headers=headers, json=payload, timeout=90) as response:
                # This will automatically raise an exception for error status codes (e.g., 401, 500).
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Error calling OpenAI Chat API: {e}")
            return "Error: Could not get a response from the language model."

async def is_content_offensive(text_to_check: str) -> bool:
    """
    Checks text against OpenAI's Moderation API. This is the application's safety guardrail.
    Returns True if the content is flagged as offensive, False otherwise.
    """
    if not text_to_check or not API_KEY:
        return False
        
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {"input": text_to_check}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(MODERATION_API_URL, headers=headers, json=payload, timeout=10) as response:
                response.raise_for_status()
                result = await response.json()
                
                # The 'flagged' key is a simple boolean summary from the Moderation API.
                is_flagged = result["results"][0]["flagged"]
                
                if is_flagged:
                    print(f"GUARDRAIL: Content flagged as offensive. Text: '{text_to_check[:100]}...'")
                return is_flagged
        except Exception as e:
            # If the moderation check itself fails, we default to "safe" to avoid
            # blocking the bot due to a temporary network or API issue.
            print(f"Warning: Moderation API call failed: {e}. Assuming content is safe as a fallback.")
            return False