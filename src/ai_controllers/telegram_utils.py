# src/ai_controllers/telegram_utils.py
import asyncio
import random
import os
from telethon import TelegramClient
from config import APP_CONFIG, TELEGRAM_USERS
from utils import StateManager

class MessageSender:
    """
    A standalone process that reads messages from the central queue and sends them
    to Telegram using the specified character's account.
    """
    def __init__(self):
        self.config = APP_CONFIG
        self.users_config = TELEGRAM_USERS
        self.destination_channel = '@' + self.config['destination_channel']
        self.state_manager = StateManager()
        
        # Create a dictionary of Telethon clients, one for each configured user
        self.clients = {
            user: TelegramClient(user, int(config["api_id"]), config["api_hash"])
            for user, config in self.users_config.items()
        }
        if not self.clients:
            raise ValueError("No Telegram clients configured. Check your .env and characters.json files.")
            
        print(f"Initialized {len(self.clients)} sender accounts.")

    async def _send_message(self, client: TelegramClient, message_obj: dict):
        """Connects a specific client and sends the message."""
        message_text = message_obj.get("message")
        if not message_text:
            print("Warning: Attempted to send an empty message.")
            return

        try:
            # The 'async with' block handles connecting and disconnecting the client
            async with client:
                # Add a human-like "typing" indicator before sending
                async with client.action(self.destination_channel, 'typing'):
                    await asyncio.sleep(random.uniform(3, 7))
                await client.send_message(self.destination_channel, message_text)
            
            # Use os.path.basename to get a clean session name for logging
            session_name = os.path.basename(client.session.filename)
            print(f"Message sent via {session_name}: '{message_text[:50]}...'")
        except Exception as e:
            print(f"Error sending message: {e}. Re-queuing message for a later attempt.")
            # If sending fails, add the message back to the queue so it isn't lost
            self.state_manager.add_message_to_queue(message_obj)

    async def run(self):
        """The main, endless loop for the sender process."""
        print("Message Sender process started...")
        while True:
            try:
                # Atomically get the next message object from the queue
                queued_item = self.state_manager.get_message_from_queue()
                
                if queued_item:
                    telegram_user = queued_item.get("telegram_user")
                    client_to_use = self.clients.get(telegram_user)
                    
                    # Fallback to a random client if the specified user isn't configured
                    if not client_to_use:
                        print(f"Warning: User '{telegram_user}' not found in clients, picking a random client.")
                        client_to_use = random.choice(list(self.clients.values()))
                    
                    await self._send_message(client_to_use, queued_item)
                    
                    # Wait for a random duration before processing the next message
                    delay = random.uniform(
                        self.config['min_send_delay_secs'],
                        self.config['max_send_delay_secs']
                    )
                    print(f"Waiting {delay:.1f} seconds before checking queue again...")
                    await asyncio.sleep(delay)
                else:
                    # If the queue is empty, wait a shorter time before checking again
                    await asyncio.sleep(15)
            
            except Exception as e:
                print(f"CRITICAL ERROR in sender loop: {e}")
                # Wait longer after a critical error before retrying
                await asyncio.sleep(60)

if __name__ == "__main__":
    sender = MessageSender()
    asyncio.run(sender.run())