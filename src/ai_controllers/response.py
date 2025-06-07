# response.py
import asyncio
import random
import traceback
import json
from datetime import datetime, timezone, timedelta
import os

import firebase_admin
from firebase_admin import credentials, firestore

from utils import StateManager
from fetch_db import get_last_message
from classify_chat import ClassifyChat
from llm_personas import PersonaManager
from initiate_topic import ConversationPlanner
from telegram_scanner import send_to_telegram, send_initiation_chat
from slack_bot import post_error_to_slack
from openai_chat import get_llm_response

class TelegramBot:
    """The main class orchestrating the Telegram bot's logic."""
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # --- Initialize All Components ---
        self.state_manager = StateManager(self.config['data_dir'])
        self.classifier = ClassifyChat(self.config['chat_classify'])
        self.persona_manager = PersonaManager()
        self.planner = ConversationPlanner(self.config, self.persona_manager)
        
        # --- Initialize Firebase ---
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.config['firebase_cred'])
            firebase_admin.initialize_app(cred, name='bot_brain_app')
        self.db = firestore.client(app=firebase_admin.get_app(name='bot_brain_app'))
        
        # --- Persistent Persona Assignments ---
        # Load persona assignments from a file to maintain consistency across restarts.
        self.assignments_file = os.path.join(self.state_manager.data_dir, 'persona_assignments.json')
        self.persona_assignments = self.state_manager.load_json(self.assignments_file)

    def _random_conversation_timestamp(self) -> list[str]:
        """
        Preserves the original logic for creating realistic, spaced-out timestamps for random talks.
        """
        current_time = datetime.now()
        random_timestamps = []
        for _ in range(5):
            if not random_timestamps:
                # First timestamp is based on current time
                last_ts_obj = current_time
            else:
                # Subsequent timestamps are based on the last one generated
                last_ts_obj = datetime.strptime(random_timestamps[-1], "%Y-%m-%d %H")

            # Add at least 16 hours to the last timestamp
            min_gap = last_ts_obj + timedelta(hours=16)
            random_seconds = random.randint(0, 3600)  # Add up to an extra hour for randomness
            next_timestamp = min_gap + timedelta(seconds=random_seconds)
            random_timestamps.append(next_timestamp.strftime("%Y-%m-%d %H"))
        return random_timestamps

    async def _handle_reaction(self, last_message: dict):
        """Handles all logic for reacting to a message."""
        text = last_message.get('text')
        sender_id = str(last_message.get('sender_id')) # Use string for JSON key compatibility

        # Check for persistent persona, or assign a new one and save it.
        if sender_id not in self.persona_assignments:
            print(f"New user {sender_id}. Assigning a random persona.")
            # Start with a random persona, can be updated later if needed
            self.persona_assignments[sender_id] = self.persona_manager.get_random_persona()
            self.state_manager.save_json(self.assignments_file, self.persona_assignments)
        
        assigned_persona = self.persona_assignments[sender_id]
        
        # Use intelligent persona selection to see if we should override the assignment for this message
        most_relevant_persona = self.persona_manager.get_most_relevant_persona(text)
        print(f"User {sender_id} (assigned {assigned_persona}) -> most relevant is {most_relevant_persona}.")

        msg_type, _ = self.classifier.predict(text)
        
        # Use the most relevant persona for the reply, not the stored one
        if msg_type == 'human':
            reply = await self.persona_manager.generate_human_like_reply(text)
        else:
            reply = await self.persona_manager.generate_reaction(most_relevant_persona, text)

        send_to_telegram(reply, self.state_manager)
        self.state_manager.log_reaction(text)

    async def _handle_initiation(self):
        """Handles all logic for initiating a new conversation."""
        print("Channel is quiet. Planning to initiate a new conversation.")
        schedule, topic = await self.planner.plan_conversation(self.db)
        
        if not schedule or not topic:
            print("Could not generate a conversation plan.")
            return

        if self.state_manager.is_topic_discussed(topic):
            print(f"Topic '{topic}' has been discussed recently. Skipping initiation.")
            return

        schedule_file = os.path.join(self.state_manager.data_dir, 'time_persona.json')
        self.state_manager.save_json(schedule_file, schedule)
        print(f"Saved new conversation plan for topic: '{topic}'")
        self.state_manager.save_discussed_topic(topic)

    async def _handle_random_talks(self):
        """Preserves and uses the original `send_random_talks` logic."""
        schedule_file = os.path.join(self.state_manager.data_dir, 'random_conversation_time.txt')
        
        schedule = self.state_manager.load_json(schedule_file)
        if not schedule:
            new_schedule = self._random_conversation_timestamp()
            self.state_manager.save_json(schedule_file, new_schedule)
            print(f"Generated new random talk schedule: {new_schedule}")
            schedule = new_schedule

        current_hour_str = datetime.now().strftime("%Y-%m-%d %H")
        
        if current_hour_str in schedule:
            print(f"Time for a scheduled random talk.")
            random_content_type = random.choice(["greetings", "queries", "discussion topic"])
            
            if random_content_type == "greetings":
                content = "Imagine you're greeting a friend in a group. Write a warm and friendly message. Keep it short within 10 words."
            else:
                persona_prompt = self.persona_manager.prompts[self.persona_manager.get_random_persona()]
                content = f"{persona_prompt} Raise a question or a topic for discussion but keep it short in 20-40 words."
            
            reply = await get_llm_response(content)
            send_to_telegram(reply, self.state_manager)
            
            schedule.remove(current_hour_str)
            self.state_manager.save_json(schedule_file, schedule)

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
                
                send_initiation_chat(self.state_manager)
                await self._handle_random_talks()

                sleep_duration = random.uniform(15 * 60, 30 * 60)
                print(f"Logic cycle complete. Sleeping for {sleep_duration/60:.1f} minutes.")
                await asyncio.sleep(sleep_duration)

            except Exception as e:
                error_trace = traceback.format_exc()
                print(f"\n--- FATAL ERROR IN MAIN LOOP ---\n{error_trace}\n")
                self.state_manager.save_error(error_trace)
                await post_error_to_slack(error_trace)
                await asyncio.sleep(60 * 10)

if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.main_loop())