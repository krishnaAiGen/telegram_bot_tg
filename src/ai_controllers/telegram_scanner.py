# telegram_scanner.py
import os
import json
from datetime import datetime
from utils import StateManager

# This function is now the primary interface for queuing any message.
def send_to_telegram(message: str, state_manager: StateManager):
    """Adds a message to the centralized sending queue."""
    if not message or "Error:" in message:
        print(f"Skipping empty or error message: {message}")
        return
    state_manager.add_message_to_queue(message)
    print(f"Message added to queue: '{message[:50]}...'")

def clean_bots(chat_messages: dict, state_manager: StateManager) -> dict:
    """
    Preserves the original logic for periodically cleaning out known bot messages.
    This now uses the StateManager to handle its counter state.
    """
    # This logic was very specific. I've refactored it to use the StateManager
    # for its counter, which is cleaner than managing its own file.
    clean_bot_state_file = os.path.join(state_manager.data_dir, 'clean_bot.json')
    clean_bot_state = state_manager.load_json(clean_bot_state_file)
    
    counter = clean_bot_state.get('counter', 10)
    
    if counter <= 0:
        counter = 10
    else:
        counter -= 1
    
    clean_bot_state['counter'] = counter
    state_manager.save_json(clean_bot_state_file, clean_bot_state)

    # The original logic to delete messages at specific counter values
    if counter in [2, 4, 6, 8, 9]:
        bot_id_list = [7347516532, 7235202962, 7661414514]
        # Create a new dictionary excluding the bot messages
        cleaned_messages = {
            key: value for key, value in chat_messages.items()
            if value.get('sender_id') not in bot_id_list
        }
        return cleaned_messages
    
    return chat_messages

def send_initiation_chat(state_manager: StateManager):
    """
    Checks the conversation schedule and queues a message if its time has come.
    This logic is preserved from the original file.
    """
    schedule_file = os.path.join(state_manager.data_dir, 'time_persona.json')
    schedule = state_manager.load_json(schedule_file)
    
    if not schedule:
        return

    now = datetime.now()
    # Use a copy of the keys to allow modification during iteration
    for timestamp_str in list(schedule.keys()):
        # The timestamp in the key is a string; convert it to a datetime object
        scheduled_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        
        if now >= scheduled_time:
            persona, message = schedule[timestamp_str]
            print(f"Scheduled message time reached for '{persona}'. Queuing message.")
            send_to_telegram(message, state_manager)
            
            # Remove the message from the schedule after queuing
            del schedule[timestamp_str]
    
    # Save the updated schedule back to the file
    state_manager.save_json(schedule_file, schedule)