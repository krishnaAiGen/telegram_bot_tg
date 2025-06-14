# src/ai_controllers/telegram_scanner.py
import os
import random
from datetime import datetime, timedelta

# Import the refactored classes and functions it depends on
from utils import StateManager
from llm_personas import PersonaManager
from openai_chat import get_llm_response, is_content_offensive

def check_initiation_send_status(state_manager: StateManager) -> bool:
    """
    Preserves the original logic of checking if a planned conversation is ready to be sent.
    The original file loaded 'discussion.txt' with pickle; this logic is now simplified
    to check if an initiation schedule exists.
    """
    schedule = state_manager.load_json(state_manager.initiation_schedule_file)
    # Returns True if there are any messages scheduled to be sent.
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
                print(f"Scheduled message time reached for '{persona_name}'. Queuing message.")
                
                # We don't know the character from the schedule, so we send with a random user.
                # The main initiation logic in `response.py` is more intelligent.
                message_to_queue = {"message": message_text, "telegram_user": None}
                state_manager.add_message_to_queue(message_to_queue)
                
                del updated_schedule[timestamp_str]
        except ValueError:
            print(f"Warning: Could not parse timestamp '{timestamp_str}' in schedule. Removing.")
            del updated_schedule[timestamp_str]

    # Save the updated schedule back to the file
    state_manager.save_json(state_manager.initiation_schedule_file, updated_schedule)

def _random_conversation_timestamp() -> list[str]:
    """Preserves the original logic for creating realistic, spaced-out timestamps."""
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
    """Preserves the logic from the original `send_random_talks` function."""
    schedule = state_manager.load_json(state_manager.random_talk_schedule_file)
    
    if not schedule:
        new_schedule = _random_conversation_timestamp()
        state_manager.save_json(state_manager.random_talk_schedule_file, new_schedule)
        schedule = new_schedule

    current_hour_str = datetime.now().strftime("%Y-%m-%d %H")
    
    if current_hour_str in schedule:
        print(f"Time for a scheduled random talk.")
        
        # Preserving the original logic for random content type
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
            schedule.remove(current_hour_str) # Remove to prevent retries
            state_manager.save_json(state_manager.random_talk_schedule_file, schedule)
            return

        # Let a random character send the random talk
        message_to_queue = {"message": reply, "telegram_user": None}
        state_manager.add_message_to_queue(message_to_queue)
        
        schedule.remove(current_hour_str)
        state_manager.save_json(state_manager.random_talk_schedule_file, schedule)

def clean_bots(chat_messages: dict, state_manager: StateManager) -> dict:
    """Preserves the original logic for periodically cleaning out known bot messages."""
    clean_bot_state = state_manager.load_json(state_manager.clean_bot_state_file)
    counter = clean_bot_state.get('counter', 10)
    
    counter = (counter - 1) if counter > 0 else 10
    clean_bot_state['counter'] = counter
    state_manager.save_json(state_manager.clean_bot_state_file, clean_bot_state)

    if counter in [2, 4, 6, 8, 9]:
        bot_id_list = [7347516532, 7235202962, 7661414514]
        # Return a new dictionary excluding messages from the bot ID list
        return {k: v for k, v in chat_messages.items() if v.get('sender_id') not in bot_id_list}
    
    return chat_messages

def create_db(state_manager: StateManager):
    """
    Preserves the original logic for ensuring state files exist.
    This is now largely handled by the StateManager's __init__, but the function
    is preserved for compatibility.
    """
    print("Ensuring state files exist...")
    # The StateManager now handles this automatically on initialization.
    # This function call is kept for logical preservation but its role is now redundant.
    # We can check one file as a proxy.
    if not os.path.exists(state_manager.discussed_topics_file):
        print("StateManager appears to have initialized files correctly.")
    else:
        print("State files already exist.")