# src/main.py
import asyncio
import time
import os
import random
from telethon import TelegramClient, events
from telethon.tl.types import User

# Import your application modules
from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services.state_manager import StateManager
from src.core_logic.llm_personas import PersonaManager
from src.core_logic.response_logic import handle_reaction, handle_initiation
from src.services.fetch_db import save_message_to_db
import firebase_admin
from firebase_admin import credentials, firestore

state = {"last_activity_time": time.time()}

async def listener_handler(event: events.NewMessage.Event, brain_queue: asyncio.Queue):
    await brain_queue.put(event.message)


async def brain_worker(brain_queue: asyncio.Queue, sender_queue: asyncio.Queue, persona_manager: PersonaManager, state_manager: StateManager, db):
    print("[BRAIN] Worker started. Waiting for messages...")
    while True:
        try:
            message = await asyncio.wait_for(brain_queue.get(), timeout=1.0)
            
            save_message_to_db(str(APP_CONFIG['telegram_group_id']), message, db)
            
            actual_sender_id = getattr(message.sender, 'id', None)
            is_known_bot = actual_sender_id in APP_CONFIG.get('known_bot_ids', [])
            
            print(f"[BRAIN] Checking msg ID {message.id} from user {actual_sender_id}. Is known bot? -> {is_known_bot}")
            
            if is_known_bot:
                state_manager.log_processed(message.id)
                brain_queue.task_done()
                continue
            
            if not state_manager.has_processed(message.id):
                # --- NEW: PROBABILITY GATE ---
                response_rate = APP_CONFIG.get("random_response_rate", 1.0)
                
                # Only apply the random check if the rate is less than 1.0
                if response_rate < 1.0:
                    roll = random.random() # Generates a float between 0.0 and 1.0
                    if roll > response_rate:
                        print(f"[BRAIN] Probability gate: Rolled {roll:.2f}, which is > {response_rate}. Choosing not to reply.")
                        # We still log the message as "processed" so we don't re-evaluate it.
                        state_manager.log_processed(message.id)
                        brain_queue.task_done()
                        continue # Skip to the next message
                    else:
                        print(f"[BRAIN] Probability gate: Rolled {roll:.2f}, which is <= {response_rate}. Proceeding with reply.")
                
                # If we pass the gate (or if the rate is 1.0), proceed as normal.
                await handle_reaction(message, sender_queue, persona_manager)
                state_manager.log_processed(message.id)
                state["last_activity_time"] = time.time()
            else:
                 print(f"[BRAIN] Message ID {message.id} has already been processed.")
            brain_queue.task_done()

        except asyncio.TimeoutError:
            now = time.time()
            if now - state['last_activity_time'] > APP_CONFIG['min_initiate_hours'] * 3600:
                print(f"[BRAIN] Inactivity detected. Calling handle_initiation...")
                await handle_initiation(sender_queue, persona_manager, state_manager, db)
                state["last_activity_time"] = now
                
        except Exception as e:
            print(f"CRITICAL ERROR in Brain Worker: {e}")
            await asyncio.sleep(10)
            
            
async def sender_worker(sender_queue: asyncio.Queue, sender_clients: dict[str, TelegramClient]):
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

            await client_to_use.send_message(APP_CONFIG['telegram_group_id'], text)
            print(f"[SENDER] Message sent successfully via {user}.")
            
            delay = random.uniform(APP_CONFIG['min_send_delay_secs'], APP_CONFIG['max_send_delay_secs'])
            await asyncio.sleep(delay)
            sender_queue.task_done()
        except Exception as e:
            print(f"CRITICAL ERROR in Sender Worker: {e}")
            await asyncio.sleep(10)

async def main():
    print("[MAIN] Initializing application...")
    brain_queue, sender_queue = asyncio.Queue(), asyncio.Queue()
    state_manager, persona_manager = StateManager(), PersonaManager()
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(APP_CONFIG['firebase_cred_path'])
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    ingestor_user, sender_users = APP_CONFIG['ingestor_bot_user'], APP_CONFIG['sender_bot_users']
    
    ingestor_client = TelegramClient(os.path.join(APP_CONFIG['data_dir'], ingestor_user), int(TELEGRAM_USERS[ingestor_user]['api_id']), TELEGRAM_USERS[ingestor_user]['api_hash'])
    sender_clients = {u: TelegramClient(os.path.join(APP_CONFIG['data_dir'], u), int(TELEGRAM_USERS[u]['api_id']), TELEGRAM_USERS[u]['api_hash']) for u in sender_users}
    
    ingestor_client.add_event_handler(lambda e: listener_handler(e, brain_queue), events.NewMessage(chats=[APP_CONFIG['telegram_group_id']]))
    
    # --- CORRECTED: Proper way to manage multiple clients and tasks ---
    
    print("[MAIN] Starting clients and background tasks...")
    
    # Start the background workers first
    brain_task = asyncio.create_task(brain_worker(brain_queue, sender_queue, persona_manager, state_manager, db))
    sender_task = asyncio.create_task(sender_worker(sender_queue, sender_clients))
    
    # Use 'async with' on the main client, which will keep the script alive
    async with ingestor_client:
        print("--- Bot running. Ingestor client is active. Press Ctrl+C to stop. ---")
        
        # Start all other sender clients in the background
        sender_client_tasks = [client.start() for client in sender_clients.values()]
        
        # Gather all tasks to run concurrently
        await asyncio.gather(
            brain_task,
            sender_task,
            *sender_client_tasks # Add the sender client startup tasks
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot shutting down.")
    except Exception as e:
        print(f"FATAL: An unhandled error occurred: {e}")