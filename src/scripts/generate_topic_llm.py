# scripts/generate_topic_llm.py
import json
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore

# Note: This script now needs to be run from the project root directory (telegram_bot_tg)
# so that the imports from the `src` package can be found.
# Command: python -m scripts.generate_topic_llm
from config.settings import APP_CONFIG
from src.services.fetch_db import get_last_100_message_texts
from src.services.openai_chat import get_llm_response

async def generate_new_topics_from_history(db, config: dict) -> list[str]:
    """
    Analyzes recent messages from a channel and uses an LLM to extract key topics.
    This function preserves the original logic but with a more robust parsing method.
    """
    print("Fetching recent chat history to generate topics...")
    chat_messages = await get_last_100_message_texts(config['source_channel'], db)
    
    # Using '\n' as a separator is better for LLM context than ''.join().
    chat_context = "\n".join([msg for msg in chat_messages if len(msg.split()) > 2])
    
    if not chat_context:
        print("No recent chat history found to generate topics from.")
        return []

    # This prompt is engineered to ask for a specific JSON output, which is more reliable than regex.
    prompt = f"""
    Analyze the following chat conversation history. Extract the two most prominent and interesting topics discussed.
    Return your answer as a JSON-formatted list of strings. For example: ["Topic about market trends", "Discussion on new features"]

    Conversation History:
    "{chat_context[:2500]}"
    """
    
    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        print(f"Attempting to generate topics (Attempt {attempts + 1}/{max_attempts})...")
        response_text = await get_llm_response(prompt)
        try:
            # Try to parse the LLM's response as a JSON list.
            topics = json.loads(response_text)
            if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
                print(f"Successfully generated topics: {topics}")
                return topics
        except json.JSONDecodeError:
            print(f"LLM did not return valid JSON. Response: {response_text}")
        
        attempts += 1
        await asyncio.sleep(2) # Wait a moment before retrying.

    print("Failed to generate topics after multiple attempts.")
    return []

async def main():
    """Main function to demonstrate running the script."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(APP_CONFIG['firebase_cred_path'])
        firebase_admin.initialize_app(cred, name='topic_generator_app')
    
    db_client = firestore.client(app=firebase_admin.get_app(name='topic_generator_app'))
    topics = await generate_new_topics_from_history(db_client, APP_CONFIG)
    
    if topics:
        print("\n--- Generated Topics ---")
        for i, topic in enumerate(topics, 1):
            print(f"{i}. {topic}")

if __name__ == "__main__":
    asyncio.run(main())