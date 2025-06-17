# src/core_logic/response.py
import asyncio
import random
import traceback
import json
from datetime import datetime, timezone, timedelta
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Import from the new, structured locations
from config.settings import APP_CONFIG
from services.utils import StateManager

from services.fetch_db import get_last_message
from services.openai_chat import get_llm_response, is_content_offensive
from services.slack_bot import post_error_to_slack
from core_logic.llm_personas import PersonaManager
from core_logic.initiate_topic import ConversationPlanner
# Import preserved helper functions
from core_logic.telegram_scanner import send_initiation_chat, send_random_talks

# Constants for Memory Management
MAX_MEMORY_TURNS = 15  # A "turn" is a user message + a bot reply (30 total messages)
MEMORY_WINDOW = 10     # When memory is full, it's trimmed to the last 10 turns (20 messages)

class TelegramBot:
    """The main class orchestrating the Telegram bot's logic."""
    def __init__(self):
        self.config = APP_CONFIG
        self.state_manager = StateManager()
        # The classifier is no longer needed in the LLM-driven selection workflow
        # self.classifier = ClassifyChat(self.config['chat_classify_model_path'])
        self.persona_manager = PersonaManager()
        self.planner = ConversationPlanner(self.persona_manager)
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='bot_brain_app')
        self.db = firestore.client(app=firebase_admin.get_app(name='bot_brain_app'))
        
        # Load persistent state for persona assignments for long-term consistency
        self.persona_assignments = self.state_manager.load_json(self.state_manager.assignments_file)

    async def _handle_reaction(self, last_message: dict):
        """Handles reacting to a message using the advanced LLM-driven workflow."""
        text = last_message.get('text')
        sender_id = str(last_message.get('sender_id'))

        # 1. Get and manage user's short-term conversation memory
        history = self.state_manager.get_user_memory(sender_id)
        if len(history) >= MAX_MEMORY_TURNS * 2:
            history = history[-MEMORY_WINDOW * 2:]
        history.append({"role": "user", "content": text})
        conversation_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        
        # 2. Prepare the list of available personas for the prompt
        available_personas = self.persona_manager.format_personas_for_prompt()

        # 3. Assemble the "Super Prompt" that asks the LLM to select a persona and reply
        super_prompt = f"""
You are a master AI assistant that embodies different expert personas within a community. Your task is to analyze the user's latest message and generate the most appropriate reply.

--- INSTRUCTIONS ---
1.  **Analyze**: Read the user's latest message and the conversation history.
2.  **Select**: Choose the single best persona from the 'Available Personas' list below to respond as.
3.  **Generate**: Adopt your chosen persona and, using the conversation history for context, generate a relevant, in-character, and helpful reply.
4.  **Format**: Provide your final answer as a single, valid JSON object with exactly two keys: "chosen_persona_name" and "reply".

--- AVAILABLE PERSONAS ---
{available_personas}

--- CONVERSATION HISTORY ---
{conversation_context}

--- YOUR JSON RESPONSE ---
"""
        # 4. Make the single LLM call to get the structured response
        response_str = await get_llm_response(super_prompt)
        
        # 5. Parse and validate the structured response
        try:
            response_data = json.loads(response_str)
            chosen_persona_name = response_data.get("chosen_persona_name")
            reply = response_data.get("reply")
            if not (chosen_persona_name and reply):
                raise ValueError("LLM response missing required keys.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response: {e}. Response was: {response_str}")
            return

        # 6. Apply the safety guardrail
        if await is_content_offensive(reply):
            print("Offensive reply blocked by guardrail.")
            return

        # 7. Find the full persona object to get the correct Telegram user
        persona_obj = self.persona_manager.get_persona_by_name(chosen_persona_name)
        telegram_user = persona_obj.get("telegram_user") if persona_obj else None
        
        # 8. Update memory and queue the safe message for sending
        history.append({"role": "assistant", "content": reply})
        self.state_manager.update_user_memory(sender_id, history)
        
        message_to_queue = {"message": reply, "telegram_user": telegram_user}
        self.state_manager.add_message_to_queue(message_to_queue)
        self.state_manager.log_reaction(text)

    async def _handle_initiation(self):
        """Handles initiating a new conversation using the ConversationPlanner."""
        print("Channel is quiet. Planning a new scheduled conversation.")
        conversation_dict, topic = await self.planner.plan_conversation(self.db, self.config)
        
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
                last_message = await get_last_message(self.config['telegram_channel'], self.db)
                initiate_now, react_now = False, False
                
                if last_message and last_message.get('date'):
                    
                    sender_id = last_message.get('sender_id')
                    if sender_id in self.config.get('known_bot_ids', []):
                        print(f"Last message was from our own bot (ID: {sender_id}). Ignoring.")
                        # Force a sleep and restart the loop to wait for a real user message
                        await asyncio.sleep(random.uniform(5 * 60, 15 * 60))
                        continue
                    time_since = datetime.now(timezone.utc) - last_message['date']
                    init_thresh = timedelta(hours=random.uniform(self.config['min_initiate_hours'], self.config['max_initiate_hours']))
                    react_thresh = timedelta(minutes=random.uniform(self.config['min_react_mins'], self.config['max_react_mins']))

                    if time_since > init_thresh:
                        initiate_now = True
                    elif time_since > react_thresh and not self.state_manager.has_reacted(last_message['text']):
                        react_now = True
                else:
                    initiate_now = True

                if initiate_now: await self._handle_initiation()
                elif react_now: await self._handle_reaction(last_message)
                
                # On every loop, check schedules for pre-planned messages
                send_initiation_chat(self.state_manager)
                await send_random_talks(self.state_manager, self.persona_manager)

                sleep_duration = random.uniform(15 * 60, 30 * 60)
                print(f"Logic cycle complete. Sleeping for {sleep_duration/60:.1f} minutes.")
                await asyncio.sleep(sleep_duration)

            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"\n--- FATAL ERROR IN MAIN LOOP ---\n{error_trace}\n")
                await post_error_to_slack(error_trace)
                self.state_manager.save_error(error_trace)
                await asyncio.sleep(60 * 10)

if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.main_loop())