# src/processes/telegram_sender.py
import asyncio
import random
import os
from telethon import TelegramClient

# --- CORRECTED IMPORTS ---
from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services.utils import StateManager

class MessageSender:
    """
    A standalone process that reads messages from the central queue and sends them
    to Telegram using the specified character's account.
    """
    def __init__(self):
        self.config = APP_CONFIG
        self.users_config = TELEGRAM_USERS
        # Use single channel config if it exists
        self.destination_channel = '@' + (self.config.get("telegram_channel") or self.config.get("destination_channel"))
        self.state_manager = StateManager()
        
        # --- CORRECTED DICTIONARY COMPREHENSION ---
        # This is the part that was likely causing the error.
        # It correctly creates a client for each user.
        self.clients = {
            user: TelegramClient(
                os.path.join(self.config['data_dir'], user), 
                int(config["api_id"]), 
                config["api_hash"]
            )
            for user, config in self.users_config.items()
        }
        if not self.clients:
            raise ValueError("No Telegram clients configured. Check your .env and characters.json files.")
            
        print(f"Sender: Initialized {len(self.clients)} sender accounts.")

    async def _send_message(self, client: TelegramClient, message_obj: dict):
        """Connects a specific client and sends the message text."""
        message_text = message_obj.get("message")
        if not message_text:
            print("Sender: Warning - Attempted to send an empty message.")
            return

        try:
            async with client:
                async with client.action(self.destination_channel, 'typing'):
                    await asyncio.sleep(random.uniform(3, 7))
                await client.send_message(self.destination_channel, message_text)
            
            session_name = os.path.basename(client.session.filename)
            print(f"Sender: Message sent via {session_name}: '{message_text[:50]}...'")
        except Exception as e:
            print(f"Sender: Error sending message: {e}. Re-queuing message for a later attempt.")
            self.state_manager.add_message_to_queue(message_obj)

    async def run(self):
        """The main, endless loop for the sender process."""
        print("Message Sender process started...")
        while True:
            try:
                queued_item = self.state_manager.get_message_from_queue()
                
                if queued_item:
                    telegram_user = queued_item.get("telegram_user")
                    client_to_use = self.clients.get(telegram_user)
                    
                    if not client_to_use:
                        print(f"Sender: User '{telegram_user}' not found or not specified. Picking a random client.")
                        client_to_use = random.choice(list(self.clients.values()))
                    
                    await self._send_message(client_to_use, queued_item)
                    
                    delay = random.uniform(
                        self.config['min_send_delay_secs'],
                        self.config['max_send_delay_secs']
                    )
                    print(f"Sender: Waiting {delay:.1f} seconds before checking queue again...")
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(15)
            
            except Exception as e:
                print(f"Sender: CRITICAL ERROR in sender loop: {e}")
                await asyncio.sleep(60)

if __name__ == "__main__":
    sender = MessageSender()
    asyncio.run(sender.run())