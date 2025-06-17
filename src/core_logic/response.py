# src/core_logic/response.py
import asyncio
import random
import traceback
import json
from datetime import datetime, timezone, timedelta
import os
import firebase_admin
from firebase_admin import credentials, firestore

# --- CORRECTED IMPORTS ---
from config.settings import APP_CONFIG
from src.services.utils import StateManager
from src.services.fetch_db import get_last_message
from src.services.openai_chat import get_llm_response, is_content_offensive
from src.services.slack_bot import post_error_to_slack
from src.core_logic.llm_personas import PersonaManager
from src.core_logic.initiate_topic import ConversationPlanner
from src.core_logic.telegram_scanner import send_initiation_chat, send_random_talks
# --- END OF CORRECTION ---

# Constants for Memory Management
MAX_MEMORY_TURNS = 15
MEMORY_WINDOW = 10

class TelegramBot:
    """The main class orchestrating the Telegram bot's logic."""
    def __init__(self):
        self.config = APP_CONFIG
        self.state_manager = StateManager()
        self.persona_manager = PersonaManager()
        self.planner = ConversationPlanner(self.persona_manager)
        
        # Use single channel config if it exists
        self.channel_name = self.config.get("telegram_channel")

        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='bot_brain_app')
        self.db = firestore.client(app=firebase_admin.get_app(name='bot_brain_app'))
        
        self.persona_assignments = self.state_manager.load_json(self.state_manager.assignments_file)
        print(f"--- Brain configured to watch channel: {self.channel_name} ---") # DEBUG PRINT

    # ... (the _handle_reaction and _handle_initiation methods are unchanged) ...
    async def _handle_reaction(self, last_message: dict):
        text = last_message.get('text')
        sender_id = str(last_message.get('sender_id'))
        history = self.state_manager.get_user_memory(sender_id)
        if len(history) >= MAX_MEMORY_TURNS * 2:
            history = history[-MEMORY_WINDOW * 2:]
        history.append({"role": "user", "content": text})
        conversation_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        available_personas = self.persona_manager.format_personas_for_prompt()
        super_prompt = f"""
You are a master AI that simulates different expert personas in an online chat group.

--- TONE AND STYLE GUIDE (VERY IMPORTANT) ---
1.  **BE HUMAN:** Write like a real person in a casual chat. Use contractions (like "it's" and "don't").
2.  **BE CONCISE:** Keep your reply short and to the point. 1-2 sentences is ideal.
3.  **HAVE PERSONALITY:** Don't just state facts. Express a real opinion or feeling based on your persona.
4.  **AVOID AI CLICHES:** Do NOT sound like a generic AI assistant. Do NOT ask open-ended questions like "How can I help?" or "Is there anything else?". Do NOT be overly formal or polite.

--- YOUR TASK ---
1.  **Analyze**: Read the user's latest message and the conversation history for context.
2.  **Select**: Choose the single best persona from the 'Available Personas' list below to respond as.
3.  **Generate**: Adopt your chosen persona's tone and generate a relevant, in-character reply that follows the Tone and Style Guide.
4.  **Format**: Provide your final answer as a single, valid JSON object with exactly two keys: "chosen_persona_name" and "reply".

--- AVAILABLE PERSONAS ---
{available_personas}

--- CONVERSATION HISTORY ---
{conversation_context}

--- YOUR JSON RESPONSE ---

"""
        response_str = await get_llm_response(super_prompt)
        try:
            response_data = json.loads(response_str)
            chosen_persona_name = response_data.get("chosen_persona_name")
            reply = response_data.get("reply")
            if not (chosen_persona_name and reply):
                raise ValueError("LLM response missing required keys.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response: {e}. Response was: {response_str}")
            return
        if await is_content_offensive(reply):
            print("Offensive reply blocked by guardrail.")
            return
        persona_obj = self.persona_manager.get_persona_by_name(chosen_persona_name)
        telegram_user = persona_obj.get("telegram_user") if persona_obj else None
        history.append({"role": "assistant", "content": reply})
        self.state_manager.update_user_memory(sender_id, history)
        message_to_queue = {"message": reply, "telegram_user": telegram_user}
        self.state_manager.add_message_to_queue(message_to_queue)
        self.state_manager.log_reaction(text)

    async def _handle_initiation(self):
        print("Channel is quiet. Planning a new scheduled conversation.")
        planner_config = self.config.copy()
        planner_config['source_channel'] = self.channel_name
        conversation_dict, topic = await self.planner.plan_conversation(self.db, planner_config)
        if not conversation_dict or not topic:
            print("Could not generate a conversation plan.")
            return
        if self.state_manager.is_topic_discussed(topic):
            print(f"Topic '{topic}' has been discussed recently. Skipping initiation.")
            return
        self.state_manager.save_initiation_schedule(conversation_dict)
        self.state_manager.save_discussed_topic(topic)

    async def main_loop(self):
        """The main, endless loop that drives the bot's actions."""
        print("Telegram Bot brain starting main loop...")
        while True:
            try:
                # --- START OF DEBUG BLOCK ---
                print("\n--- Checking for messages... ---")
                last_message = await get_last_message(self.channel_name, self.db)
                
                if last_message:
                    print(f"Found last message: '{last_message.get('text', 'No text')[:40]}...'")
                else:
                    print("Last message is None. (Is the channel name in .env correct? Is the DB collection empty?)")
                # --- END OF DEBUG BLOCK ---

                initiate_now, react_now = False, False
                
                if last_message and last_message.get('date'):
                    sender_id = last_message.get('sender_id')
                    if sender_id and sender_id in self.config.get('known_bot_ids', []):
                        print(f"DEBUG: Last message is from our own bot (ID: {sender_id}). Ignoring.")
                        await asyncio.sleep(random.uniform(10,20))
                        continue

                    time_since = datetime.now(timezone.utc) - last_message['date']
                    init_thresh = timedelta(hours=random.uniform(self.config['min_initiate_hours'], self.config['max_initiate_hours']))
                    react_thresh = timedelta(minutes=random.uniform(self.config['min_react_mins'], self.config['max_react_mins']))
                    
                    # --- MORE DEBUG PRINTS ---
                    print(f"DEBUG: Time since last message: {time_since}")
                    print(f"DEBUG: React threshold: {react_thresh}")
                    
                    if time_since > init_thresh:
                        initiate_now = True
                    elif time_since > react_thresh and not self.state_manager.has_reacted(last_message['text']):
                        react_now = True
                else:
                    initiate_now = True

                print(f"DEBUG: Decision -> Initiate: {initiate_now}, React: {react_now}") # Final decision print

                if initiate_now: await self._handle_initiation()
                elif react_now: await self._handle_reaction(last_message)
                
                send_initiation_chat(self.state_manager)
                await send_random_talks(self.state_manager, self.persona_manager)

                sleep_duration = random.uniform(10, 30)
                print(f"Logic cycle complete. Sleeping for {sleep_duration/60:.1f} minutes.")
                await asyncio.sleep(sleep_duration)

            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"\n--- FATAL ERROR IN MAIN LOOP ---\n{error_trace}\n")
                if self.config.get("slack_webhook_url"):
                    await post_error_to_slack(error_trace)
                self.state_manager.save_error(error_trace)
                await asyncio.sleep(60 * 10)

if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.main_loop())