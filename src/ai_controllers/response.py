# src/ai_controllers/response.py
import asyncio
import random
import traceback
from datetime import datetime, timezone, timedelta
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Import from our new centralized config and refactored modules
from config import APP_CONFIG
from utils import StateManager
from fetch_db import get_last_message
from classify_chat import ClassifyChat
from llm_personas import PersonaManager
from initiate_topic import ConversationPlanner
from openai_chat import get_llm_response, is_content_offensive
from slack_bot import post_error_to_slack
from telegram_scanner import send_initiation_chat, send_random_talks

# Constants for Memory Management
MAX_MEMORY_TURNS = 15  # A "turn" is a user message + a bot reply (30 total messages)
MEMORY_WINDOW = 10     # When memory is full, keep the last 10 turns (20 messages)

class TelegramBot:
    """The main class orchestrating the Telegram bot's logic."""
    def __init__(self):
        self.config = APP_CONFIG
        self.state_manager = StateManager()
        self.classifier = ClassifyChat(self.config['chat_classify_model_path'])
        self.persona_manager = PersonaManager()
        self.planner = ConversationPlanner(self.persona_manager)
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred_path'])
            firebase_admin.initialize_app(cred, name='bot_brain_app')
        self.db = firestore.client(app=firebase_admin.get_app(name='bot_brain_app'))
        
        # Load persistent state for persona assignments
        self.persona_assignments = self.state_manager.load_json(self.state_manager.assignments_file)

    async def _handle_reaction(self, last_message: dict):
        """Handles reacting to a message, with memory and a safety guardrail."""
        text = last_message.get('text')
        sender_id = str(last_message.get('sender_id'))

        # 1. Get and manage user's conversation memory
        history = self.state_manager.get_user_memory(sender_id)
        if len(history) >= MAX_MEMORY_TURNS * 2:
            history = history[-MEMORY_WINDOW * 2:]
        history.append({"role": "user", "content": text})
        
        conversation_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        
        # 2. Select persona and generate reply
        persona_obj = self.persona_manager.get_most_relevant_persona(text)
        if not persona_obj: return

        print(f"Reacting with persona '{persona_obj['persona_name']}' from character '{persona_obj['character_name']}'.")
        
        msg_type, _ = self.classifier.predict(text)
        if msg_type == 'human':
            reply = await self.persona_manager.generate_human_like_reply(text)
        else:
            reply = await self.persona_manager.generate_reaction(persona_obj, conversation_context)

        # 3. Check reply with offensive content guardrail
        if await is_content_offensive(reply):
            print("Offensive reply blocked by guardrail.")
            return

        # 4. Update memory and queue the safe message
        history.append({"role": "assistant", "content": reply})
        self.state_manager.update_user_memory(sender_id, history)
        
        message_to_queue = {"message": reply, "telegram_user": persona_obj.get("telegram_user")}
        self.state_manager.add_message_to_queue(message_to_queue)
        self.state_manager.log_reaction(text)

    async def _handle_initiation(self):
        """Handles initiating a new conversation."""
        print("Channel is quiet. Planning to initiate a new conversation.")
        conversation_dict, topic = await self.planner.plan_conversation(self.db, self.config)
        
        if not conversation_dict or not topic:
            print("Could not generate a conversation plan.")
            return

        if self.state_manager.is_topic_discussed(topic):
            print(f"Topic '{topic}' has been discussed recently. Skipping initiation.")
            return

        # The planner returns a dictionary that the state manager knows how to schedule
        self.state_manager.save_initiation_schedule(conversation_dict)
        self.state_manager.save_discussed_topic(topic)

    async def main_loop(self):
        """The main, endless loop that drives the bot's actions."""
        print("Telegram Bot brain starting main loop...")
        while True:
            try:
                last_message = await get_last_message(self.config['source_channel'], self.db)
                initiate_now, react_now = False, False
                
                if last_message and last_message.get('date'):
                    time_since = datetime.now(timezone.utc) - last_message['date']
                    init_thresh = timedelta(hours=random.uniform(self.config['min_initiate_hours'], self.config['max_initiate_hours']))
                    react_thresh = timedelta(minutes=random.uniform(self.config['min_react_mins'], self.config['max_react_mins']))

                    if time_since > init_thresh:
                        initiate_now = True
                    elif time_since > react_thresh and not self.state_manager.has_reacted(last_message['text']):
                        react_now = True
                else:
                    initiate_now = True

                if initiate_now:
                    await self._handle_initiation()
                elif react_now:
                    await self._handle_reaction(last_message)
                
                # On every loop, check if any scheduled messages need to be sent
                send_initiation_chat(self.state_manager)
                await send_random_talks(self.state_manager, self.persona_manager)

                sleep_duration = random.uniform(15 * 60, 30 * 60)
                print(f"Logic cycle complete. Sleeping for {sleep_duration/60:.1f} minutes.")
                await asyncio.sleep(sleep_duration)

            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"\n--- FATAL ERROR IN MAIN LOOP ---\n{error_trace}\n")
                await post_error_to_slack(error_trace)
                await asyncio.sleep(60 * 10)

if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.main_loop())