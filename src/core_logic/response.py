# src/core_logic/response.py
import asyncio
import random
import traceback
import json
import time
from firebase_admin import credentials, firestore
import firebase_admin
# Added these necessary imports
from config.settings import APP_CONFIG, CHARACTERS_DATA
from src.services.utils import StateManager
from src.services.openai_chat import get_llm_response, is_content_offensive
from src.core_logic.llm_personas import PersonaManager
from src.services.fetch_db import get_last_100_message_texts # Used for context

class TelegramBot:
    def __init__(self):
        self.config = APP_CONFIG
        self.state_manager = StateManager()
        self.persona_manager = PersonaManager()
        self.last_initiation_time = time.time()
        self.channel_name = self.config.get("telegram_channel")
        # Need to initialize the db for fetching context
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='bot_brain_app')
        self.db = firestore.client(app=firebase_admin.get_app(name='bot_brain_app'))
        print("--- Brain Initialized (Event-Driven Mode) ---")

    async def _handle_reaction(self, message_data: dict):
        text = message_data.get('text')
        print(f"--- Reacting to Message ID: {message_data['message_id']} | Text: '{text[:40]}...' ---")

        persona_profiles = []
        for p in self.persona_manager.all_personas:
            profile = f"""
### Persona: {p['persona_name']}
**Role:** {p.get('role', 'N/A')}
**Signature Voice:** Tone is {p.get('signature_voice', {}).get('tone', 'neutral')}, style is {p.get('signature_voice', {}).get('style', 'direct')}.
**Use Emojis:** {p.get('allow_emojis', False)}
**Example Reply:** "{p.get('examples', [{}])[0].get('assistant', 'N/A')}"
"""
            persona_profiles.append(profile)
        available_personas_text = "\n".join(persona_profiles)

        super_prompt = f"""
You are a master AI that simulates different expert personas in an online chat group. Your task is to select the BEST persona and generate a human-like, in-character reply.
--- TONE AND STYLE GUIDE (MANDATORY) ---
1.  **BE HUMAN & CONCISE:** Write 1-2 casual sentences. Use contractions (it's, don't).
2.  **EMBODY THE PERSONA:** Fully adopt the chosen persona's voice, tone, and examples.
3.  **AVOID AI CLICHES:** DO NOT sound like a generic assistant.
4.  **EMOJI RULE:** If the chosen persona's "Use Emojis" is `true`, you may use them. If `false`, you must not.
--- YOUR TASK ---
1.  **Analyze**: Read the user's latest message: "{text}".
2.  **Review Personas**: Read the detailed persona profiles below.
3.  **Select**: Choose the SINGLE best persona to respond.
4.  **Generate**: Generate a reply that PERFECTLY matches the chosen persona's voice.
5.  **Format**: Provide your final answer as a single, valid JSON object with exactly two keys: "chosen_persona_name" and "reply".
--- AVAILABLE PERSONA PROFILES ---
{available_personas_text}
--- YOUR JSON RESPONSE ---
"""
        response_str = await get_llm_response(super_prompt)
        try:
            response_data = json.loads(response_str)
            chosen_persona_name = response_data.get("chosen_persona_name")
            reply = response_data.get("reply")
            if not (chosen_persona_name and reply): raise ValueError("Missing keys.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response: {e}. Response: {response_str}")
            return

        if await is_content_offensive(reply):
            return

        persona_obj = self.persona_manager.get_persona_by_name(chosen_persona_name)
        telegram_user = persona_obj.get("telegram_user") if persona_obj else "trial_account"
        
        message_to_send = {"message": reply, "telegram_user": telegram_user}
        self.state_manager.add_message_to_sender_queue(message_to_send)
        print(f"Generated reply for message {message_data['message_id']}. Queued for sender.")

    async def _handle_initiation(self):
        """Dynamically generates and posts a new topic to restart conversation."""
        print("Planning to initiate a new topic...")
        
        # 1. Get context from recent messages
        messages = await get_last_100_message_texts(self.channel_name, self.db)
        chat_history = "\n".join(messages)
        
        # 2. Use our utility persona to generate a topic
        topic_prompt_instruction = CHARACTERS_DATA["utility_personas"]["generate_topic"]
        topic_prompt = f"{topic_prompt_instruction}\n\nHere is the recent chat history:\n\"\"\"\n{chat_history[:2000]}\n\"\"\""
        
        new_topic = await get_llm_response(topic_prompt)
        if not new_topic or "Error:" in new_topic:
            print("Could not generate a new topic.")
            return

        print(f"Generated new topic: {new_topic}")
        
        # 3. Choose a random persona to post the topic starter
        random_persona = self.persona_manager.get_random_persona()
        if not random_persona: return
        
        # 4. Ask that persona to craft a message about the new topic
        starter_prompt = f"""
Your persona is: {random_persona['persona_name']} ({random_persona['role']}).
Your task is to start a conversation about the following topic: "{new_topic}".
Write a short, casual, open-ended question or statement (1-2 sentences) to get people talking.
Follow your persona's voice and emoji rules. Do not reveal your identity.
"""
        starter_message = await get_llm_response(starter_prompt)
        
        initiation_message = {"message": starter_message, "telegram_user": random_persona.get("telegram_user")}
        self.state_manager.add_message_to_sender_queue(initiation_message)
        print(f"Queued initiation message from {random_persona['persona_name']}.")

    async def main_loop(self):
        # This loop is now correct from the previous step.
        pass # Full code provided in previous responses

if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.main_loop())