import asyncio
import time
import os
import random
from telethon import TelegramClient, events

from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services.state_manager import StateManager
from src.core_logic.llm_personas import PersonaManager
from src.core_logic.response_logic import handle_reaction, handle_initiation

# --- Main Application State ---
state = {"last_activity_time": time.time()}

# --- Worker 1: Listener (Ingestor Logic) ---
async def listener_handler(event, brain_queue: asyncio.Queue):
    """Event handler that puts new messages into the brain_queue."""
    print(f"Listener: New message (ID: {event.message.id}). Queuing for brain.")
    await brain_queue.put(event.message)

# --- Worker 2: Brain (Response & Initiation Logic) ---
async def brain_worker(brain_queue: asyncio.Queue, sender_queue: asyncio.Queue, persona_manager: PersonaManager, state_manager: StateManager):
    """The core logic loop that reacts to messages and initiates topics."""
    print("Brain Worker: Started.")
    while True:
        try:
            message = await asyncio.wait_for(brain_queue.get(), timeout=1.0)
            
            # --- REACTIVE LOGIC ---
            sender_id = message.sender_id
            if sender_id in APP_CONFIG.get('known_bot_ids', []):
                # Optionally, add a small chance to reply to bots anyway
                if random.random() > 0.1: # 90% chance to ignore
                    print(f"Brain: Ignoring message from known bot ID {sender_id}.")
                    state_manager.log_processed(message.id)
                    brain_queue.task_done()
                    continue
            
            if not state_manager.has_processed(message.id):
                await handle_reaction(message, sender_queue, persona_manager)
                state_manager.log_processed(message.id)
                state["last_activity_time"] = time.time()
            brain_queue.task_done()

        except asyncio.TimeoutError:
            # --- PROACTIVE LOGIC (No message received) ---
            init_thresh_seconds = APP_CONFIG['min_initiate_hours'] * 3600
            if time.time() - state["last_activity_time"] > init_thresh_seconds:
                print("Brain: Inactivity detected. Planning to initiate a new topic.")
                await handle_initiation(sender_queue, persona_manager)
                state["last_activity_time"] = time.time()
        
        except Exception as e:
            print(f"CRITICAL ERROR in Brain Worker: {e}")
            await asyncio.sleep(10)

# --- Worker 3: Sender (Message Sending Logic) ---
async def sender_worker(sender_queue: asyncio.Queue, sender_clients: dict):
    """Pulls messages from the sender_queue and sends them using the correct bot."""
    print("Sender Worker: Started.")
    while True:
        try:
            msg_to_send = await sender_queue.get()
            user = msg_to_send.get("telegram_user")
            text = msg_to_send.get("message")

            if not text or not user:
                print(f"Sender: Invalid message object received: {msg_to_send}")
                sender_queue.task_done()
                continue
            
            client_to_use = sender_clients.get(user)
            if not client_to_use:
                print(f"Sender: User '{user}' not found in available sender clients.")
                sender_queue.task_done()
                continue

            async with client_to_use:
                async with client_to_use.action(f"@{APP_CONFIG['telegram_channel']}", 'typing'):
                    await asyncio.sleep(random.uniform(2, 5))
                await client_to_use.send_message(f"@{APP_CONFIG['telegram_channel']}", text)
            print(f"Sender: Message sent via {user}: '{text[:40]}...'")
            
            delay = random.uniform(APP_CONFIG['min_send_delay_secs'], APP_CONFIG['max_send_delay_secs'])
            await asyncio.sleep(delay)
            sender_queue.task_done()
        except Exception as e:
            print(f"CRITICAL ERROR in Sender Worker: {e}")
            await asyncio.sleep(10)

# --- Main Orchestrator ---
async def main():
    """Initializes and runs all components of the bot."""
    brain_queue = asyncio.Queue()
    sender_queue = asyncio.Queue()
    state_manager = StateManager()
    persona_manager = PersonaManager()

    ingestor_user = APP_CONFIG['ingestor_bot_user']
    sender_users = APP_CONFIG['sender_bot_users']
    
    ingestor_client = TelegramClient(
        os.path.join(APP_CONFIG['data_dir'], ingestor_user),
        int(TELEGRAM_USERS[ingestor_user]['api_id']),
        TELEGRAM_USERS[ingestor_user]['api_hash']
    )
    sender_clients = {
        user: TelegramClient(
            os.path.join(APP_CONFIG['data_dir'], user),
            int(TELEGRAM_USERS[user]['api_id']),
            TELEGRAM_USERS[user]['api_hash']
        ) for user in sender_users
    }
    
    ingestor_client.add_event_handler(
        lambda event: listener_handler(event, brain_queue),
        events.NewMessage(chats=[f"@{APP_CONFIG['telegram_channel']}"])
    )

    brain_task = asyncio.create_task(brain_worker(brain_queue, sender_queue, persona_manager, state_manager))
    sender_task = asyncio.create_task(sender_worker(sender_queue, sender_clients))
    
    print("--- Bot initialized. Starting all clients. Press Ctrl+C to stop. ---")
    
    all_clients = [ingestor_client] + list(sender_clients.values())
    await asyncio.gather(
        *(client.start() for client in all_clients),
        brain_task,
        sender_task
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot shutting down.")