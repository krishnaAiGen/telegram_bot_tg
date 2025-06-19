# src/main.py
import asyncio
import time
import os
from telethon import TelegramClient, events

# Import your application modules
from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services.state_manager import StateManager
from src.core_logic.llm_personas import PersonaManager

import firebase_admin
from firebase_admin import credentials, firestore

from src.workers.listener import listener_handler
from src.workers.brain import brain_worker
from src.workers.sender import sender_worker


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