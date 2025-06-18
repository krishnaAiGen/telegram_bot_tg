# src/main.py
import asyncio
import time
import os
import random
from collections import deque
from telethon import TelegramClient, events
from telethon.tl.types import User, PeerUser

# Import your application modules
from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services.state_manager import StateManager
from src.core_logic.llm_personas import PersonaManager
from src.core_logic.response_logic import handle_reaction, handle_initiation

# --- Main Application State ---
state = {"last_activity_time": time.time()}

# --- Worker 1: Listener (Ingestor Logic) ---
async def listener_handler(event: events.NewMessage.Event, brain_queue: asyncio.Queue, sent_messages_cache: deque):
    """Puts new messages into the brain_queue, ignoring self-sent messages."""
    # --- NEW: Check against the cache of recently sent messages ---
    if event.message.text and event.message.text in sent_messages_cache:
        print(f"[LISTENER] Ignoring own message detected in cache: '{event.message.text[:30]}...'")
        sent_messages_cache.remove(event.message.text)  # Remove to allow a real user to send the same text
        return

    print(f"[LISTENER] New message received (ID: {event.message.id}). Adding to brain_queue.")
    await brain_queue.put(event.message)

# --- Worker 2: Brain (Response & Initiation Logic) ---
async def brain_worker(brain_queue: asyncio.Queue, sender_queue: asyncio.Queue, persona_manager: PersonaManager, state_manager: StateManager):
    """The core logic loop that reacts to messages and initiates topics."""
    print("[BRAIN] Worker started. Waiting for messages...")
    while True:
        try:
            message = await asyncio.wait_for(brain_queue.get(), timeout=1.0)
            print(f"[BRAIN] Pulled message ID {message.id} from queue.")
            
            # This check is now a fallback, the cache is the primary guard.
            sender_id_attr = getattr(message.sender, 'id', None)
            from_id_peer = getattr(message, 'from_id', None)
            from_id_attr = getattr(from_id_peer, 'user_id', None) if isinstance(from_id_peer, PeerUser) else None
            actual_sender_id = sender_id_attr or from_id_attr
            
            if actual_sender_id in APP_CONFIG.get('known_bot_ids', []):
                print(f"[BRAIN] Fallback check: Sender {actual_sender_id} is a known bot. Ignoring.")
                state_manager.log_processed(message.id)
                brain_queue.task_done()
                continue
            
            if not state_manager.has_processed(message.id):
                print(f"[BRAIN] Message ID {message.id} is new. Calling handle_reaction...")
                await handle_reaction(message, sender_queue, persona_manager)
                state_manager.log_processed(message.id)
                state["last_activity_time"] = time.time()
            else:
                 print(f"[BRAIN] Message ID {message.id} has already been processed. Skipping.")
            brain_queue.task_done()

        except asyncio.TimeoutError:
            now = time.time()
            if now - state['last_activity_time'] > APP_CONFIG['min_initiate_hours'] * 3600:
                print(f"[BRAIN] Inactivity detected. Calling handle_initiation...")
                await handle_initiation(sender_queue, persona_manager)
                state["last_activity_time"] = now
        
        except Exception as e:
            print(f"CRITICAL ERROR in Brain Worker: {e}")
            await asyncio.sleep(10)

# --- Worker 3: Sender (Message Sending Logic) ---
async def sender_worker(sender_queue: asyncio.Queue, sender_clients: dict[str, TelegramClient], sent_messages_cache: deque):
    """Pulls messages from the sender_queue and sends them, updating the cache."""
    print("[SENDER] Worker started. Waiting for messages to send...")
    while True:
        try:
            msg = await sender_queue.get()
            user, text = msg.get("telegram_user"), msg.get("message")

            if not text or not user:
                sender_queue.task_done()
                continue
            
            client_to_use = sender_clients.get(user)
            if not client_to_use or not client_to_use.is_connected():
                sender_queue.task_done()
                continue

            await client_to_use.send_message(f"@{APP_CONFIG['telegram_channel']}", text)
            print(f"[SENDER] Message sent successfully via {user}.")
            
            # --- NEW: Add the sent message text to the cache ---
            sent_messages_cache.append(text)
            print(f"[SENDER] Added message to cache. Cache size: {len(sent_messages_cache)}")
            
            delay = random.uniform(APP_CONFIG['min_send_delay_secs'], APP_CONFIG['max_send_delay_secs'])
            await asyncio.sleep(delay)
            sender_queue.task_done()
        except Exception as e:
            print(f"CRITICAL ERROR in Sender Worker: {e}")
            await asyncio.sleep(10)

# --- Main Orchestrator ---
async def main():
    """Initializes and runs all components of the bot."""
    print("[MAIN] Initializing application...")
    brain_queue, sender_queue = asyncio.Queue(), asyncio.Queue()
    # --- NEW: Create the shared message cache ---
    sent_messages_cache = deque(maxlen=10) # Holds the last 10 sent message texts
    
    state_manager, persona_manager = StateManager(), PersonaManager()
    
    ingestor_user, sender_users = APP_CONFIG['ingestor_bot_user'], APP_CONFIG['sender_bot_users']
    
    ingestor_client = TelegramClient(os.path.join(APP_CONFIG['data_dir'], ingestor_user), int(TELEGRAM_USERS[ingestor_user]['api_id']), TELEGRAM_USERS[ingestor_user]['api_hash'])
    sender_clients = {u: TelegramClient(os.path.join(APP_CONFIG['data_dir'], u), int(TELEGRAM_USERS[u]['api_id']), TELEGRAM_USERS[u]['api_hash']) for u in sender_users}
    
    # --- MODIFIED: Pass the cache to the listener ---
    ingestor_client.add_event_handler(lambda e: listener_handler(e, brain_queue, sent_messages_cache), events.NewMessage(chats=[f"@{APP_CONFIG['telegram_channel']}"]))
    
    print("[MAIN] Starting clients...")
    all_clients = [ingestor_client] + list(sender_clients.values())
    for client in all_clients:
        await client.start()

    print("[MAIN] Creating background tasks...")
    brain_task = asyncio.create_task(brain_worker(brain_queue, sender_queue, persona_manager, state_manager))
    # --- MODIFIED: Pass the cache to the sender ---
    sender_task = asyncio.create_task(sender_worker(sender_queue, sender_clients, sent_messages_cache))
    
    print("--- Bot running. Press Ctrl+C to stop. ---")
    
    running_tasks = [client.run_until_disconnected() for client in all_clients]
    await asyncio.gather(*running_tasks, brain_task, sender_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot shutting down.")
    except Exception as e:
        print(f"FATAL: An unhandled error occurred: {e}")