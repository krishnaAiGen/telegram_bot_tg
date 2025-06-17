# src/core_logic/telegram_scanner.py
import os
import random
from datetime import datetime, timedelta

# Import the refactored classes and functions it depends on
from src.services.utils import StateManager
from config.settings import APP_CONFIG

from src.core_logic.llm_personas import PersonaManager
from src.services.openai_chat import get_llm_response, is_content_offensive

def check_initiation_send_status(state_manager: StateManager) -> bool:
    """
    Preserves the original logic of checking if a planned conversation is ready to be sent.
    It checks if an initiation schedule exists and has content.
    """
    schedule = state_manager.load_json(state_manager.initiation_schedule_file)
    return len(schedule) > 0

def send_initiation_chat(state_manager: StateManager):
    """
    Checks the conversation schedule and queues a message if its time has come.
    This logic is preserved from the original file.
    """
    schedule = state_manager.load_json(state_manager.initiation_schedule_file)
    if not schedule:
        return

    now = datetime.now()
    updated_schedule = schedule.copy()
    
    for timestamp_str, details in schedule.items():
        try:
            scheduled_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            if now >= scheduled_time:
                persona_name, message_text = details
                # In the original logic, the character/user was not stored in the schedule.
                # To preserve this, we queue the message with 'telegram_user: None',
                # which signals the sender to pick a random account.
                print(f"Scheduled message time reached for '{persona_name}'. Queuing message.")
                message_to_queue = {"message": message_text, "telegram_user": None}
                state_manager.add_message_to_queue(message_to_queue)
                
                # Remove the message from the schedule after queuing.
                del updated_schedule[timestamp_str]
        except ValueError:
            print(f"Warning: Could not parse timestamp '{timestamp_str}' in schedule. Removing.")
            del updated_schedule[timestamp_str]

    # Save the updated schedule (with the sent message removed) back to the file.
    state_manager.save_json(state_manager.initiation_schedule_file, updated_schedule)

def _random_conversation_timestamp() -> list[str]:
    """Preserves the original algorithm for creating realistic, spaced-out timestamps."""
    current_time = datetime.now()
    random_timestamps = []
    last_ts_obj = current_time
    
    for _ in range(5):
        min_gap = last_ts_obj + timedelta(hours=16)
        random_seconds = random.randint(0, 3600)
        next_timestamp = min_gap + timedelta(seconds=random_seconds)
        random_timestamps.append(next_timestamp.strftime("%Y-%m-%d %H"))
        last_ts_obj = next_timestamp
        
    return random_timestamps

async def send_random_talks(state_manager: StateManager, persona_manager: PersonaManager):
    """Preserves the complete logic for the 'send_random_talks' feature."""
    schedule = state_manager.load_json(state_manager.random_talk_schedule_file)
    
    if not schedule:
        new_schedule = _random_conversation_timestamp()
        state_manager.save_json(state_manager.random_talk_schedule_file, new_schedule)
        schedule = new_schedule

    current_hour_str = datetime.now().strftime("%Y-%m-%d %H")
    
    if current_hour_str in schedule:
        print(f"Time for a scheduled random talk.")
        
        # Preserving the original weighted random choice for content type.
        random_content_dict = {"1": "greetings", "2": "queries", "3": "discussion topic"}
        random_content_type = random_content_dict[str(random.randint(1, 3))]
        
        if random_content_type == "greetings":
            content = "Imagine you're greeting a friend in a group. Write a warm and friendly message. Keep it short, within 10 words."
        else:
            persona_obj = persona_manager.get_random_persona()
            persona_prompt = persona_obj['description']
            content = f"{persona_prompt} Raise a question or a topic for discussion but keep it short, in 20-40 words."
        
        reply = await get_llm_response(content)
        
        if await is_content_offensive(reply):
            print("Offensive random talk blocked.")
            schedule.remove(current_hour_str)
            state_manager.save_json(state_manager.random_talk_schedule_file, schedule)
            return

        # Let a random character send the random talk.
        message_to_queue = {"message": reply, "telegram_user": None}
        state_manager.add_message_to_queue(message_to_queue)
        
        schedule.remove(current_hour_str)
        state_manager.save_json(state_manager.random_talk_schedule_file, schedule)

def clean_bots(chat_messages: dict, state_manager: StateManager) -> dict:
    """Preserves the original logic for periodically cleaning out known bot messages from a dictionary."""
    clean_bot_state = state_manager.load_json(state_manager.clean_bot_state_file)
    counter = clean_bot_state.get('counter', 10)
    
    counter = (counter - 1) if counter > 0 else 10
    clean_bot_state['counter'] = counter
    state_manager.save_json(state_manager.clean_bot_state_file, clean_bot_state)

    if counter in [2, 4, 6, 8, 9]:
        bot_id_list = [7347516532, 7235202962, 7661414514]
        return {k: v for k, v in chat_messages.items() if v.get('sender_id') not in bot_id_list}
    
    return chat_messages

def create_db(state_manager: StateManager):
    """
    Preserves the original function for ensuring state files exist.
    Its role is now handled by the StateManager's constructor, but it is kept for compatibility.
    """
    print("Verifying state file initialization...")
    # The StateManager now handles this automatically. This is a no-op for verification.
    if os.path.exists(state_manager.discussed_topics_file):
        print("State files appear to be correctly initialized.")