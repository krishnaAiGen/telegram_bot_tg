# src/services/grok_chat.py
import aiohttp
import os
from config.settings import APP_CONFIG

# Load the API key and define the URL
GROK_API_KEY = APP_CONFIG.get("xai_api_key")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

async def get_grok_response(content: str, model: str = "llama3-70b-8192") -> str:
    """
    Gets a response from the Grok API.
    Returns a placeholder message if the API key is not configured.
    """
    # 1. Check if the API key is missing or is still the placeholder value.
    if not GROK_API_KEY or GROK_API_KEY == "YOUR_GROK_API_KEY_HERE":
        print("[GROK] API key not configured. Returning placeholder message.")
        return "Grok API not configured. This question requires real-time data."

    # 2. Prepare the request headers and payload in the format Grok expects.
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = [{"role": "user", "content": content}]
    payload = {"model": model, "messages": messages}

    timeout = aiohttp.ClientTimeout(total=90)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROK_API_URL, headers=headers, json=payload, timeout=timeout) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Error calling Grok API: {e}")
            return f"Error: Could not get a response from Grok. Details: {e}"