# src/ai_controllers/generate_topic_llm.py
import json
import asyncio
from fetch_db import get_last_100_message_texts
from openai_chat import get_llm_response
import firebase_admin
from firebase_admin import credentials, firestore
from config import APP_CONFIG

async def generate_new_topics_from_history(db, config: dict) -> list[str]:
    """
    Analyzes recent messages from a channel and uses an LLM to extract key topics.
    """
    print("Fetching recent chat history to generate topics...")
    chat_messages = await get_last_100_message_texts(config['source_channel'], db)
    chat_context = "\n".join([msg for msg in chat_messages if len(msg.split()) > 2])
    
    if not chat_context:
        print("No recent chat history found to generate topics from.")
        return []

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
            topics = json.loads(response_text)
            if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
                print(f"Successfully generated topics: {topics}")
                return topics
        except json.JSONDecodeError:
            print(f"LLM did not return valid JSON. Response: {response_text}")
        
        attempts += 1
        await asyncio.sleep(2)

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