# openai_chat.py
import json
import aiohttp

with open('config.json', 'r') as json_file:
    config = json.load(json_file)

API_KEY = config["openai_api_key"]
API_URL = "https://api.openai.com/v1/chat/completions"

async def get_llm_response(content: str, model: str = "gpt-4", max_tokens: int = 300) -> str:
    """Asynchronously gets a response from the OpenAI Chat Completion API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, headers=headers, json=payload, timeout=90) as response:
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
        except aiohttp.ClientError as e:
            print(f"Error calling OpenAI API: {e}")
            return "Error: Could not get a response from the LLM."
        except Exception as e:
            print(f"An unexpected error occurred during OpenAI call: {e}")
            return "Error: An unexpected issue occurred."