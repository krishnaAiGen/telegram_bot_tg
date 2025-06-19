import asyncio
import time
import random
from config.settings import APP_CONFIG
from src.services.state_manager import StateManager
from src.core_logic.llm_personas import PersonaManager
from src.core_logic.response_logic import handle_reaction, handle_initiation
from src.services.fetch_db import save_message_to_db



async def brain_worker(brain_queue: asyncio.Queue, sender_queue: asyncio.Queue, persona_manager: PersonaManager, state_manager: StateManager, db):
    print("[BRAIN] Worker started. Waiting for messages...")
    bot_state = state_manager.load_bot_state()
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
                bot_state["last_activity_time"] = time.time()
                state_manager.save_bot_state(bot_state)
            else:
                 print(f"[BRAIN] Message ID {message.id} has already been processed.")
            brain_queue.task_done()

        except asyncio.TimeoutError:
            now = time.time()
            # --- MODIFIED: Use persistent state for check ---
            if now - bot_state['last_activity_time'] > APP_CONFIG['min_initiate_hours'] * 3600:
                await handle_initiation(sender_queue, persona_manager, state_manager, db)
                # --- MODIFIED: Update and save state ---
                bot_state["last_activity_time"] = now
                state_manager.save_bot_state(bot_state)
        except Exception as e:
            print(f"CRITICAL ERROR in Brain Worker: {e}")
            await asyncio.sleep(10)