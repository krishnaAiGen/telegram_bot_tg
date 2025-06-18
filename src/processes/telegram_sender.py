# src/processes/telegram_sender.py
import asyncio
import random
import os
from telethon import TelegramClient

from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.services import utils

class MessageSender:
    """A standalone process that reads messages from the sender queue and sends them."""
    def __init__(self):
        self.config = APP_CONFIG
        self.users_config = TELEGRAM_USERS
        
        self.data_dir = utils.get_data_dir(self.config)
        self.sender_queue_path = os.path.join(self.data_dir, 'sender_queue.json')
        
        self.destination_channel = '@' + self.config.get("telegram_channel")
        
        self.clients = {
            user: TelegramClient(
                os.path.join(self.data_dir, user), 
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
            # The 'async with' block is the safest way to manage the client connection
            async with client:
                async with client.action(self.destination_channel, 'typing'):
                    await asyncio.sleep(random.uniform(3, 7))
                await client.send_message(self.destination_channel, message_text)
            
            session_name = os.path.basename(client.session.filename)
            print(f"Sender: Message sent via {session_name}: '{message_text[:50]}...'")

        except Exception as e:
            print(f"Sender: Error sending message: {e}. Re-queuing message for a later attempt.")
            # Add the message back to the front of the queue if it fails
            queue = utils.load_json(self.sender_queue_path)
            queue.insert(0, message_obj)
            utils.save_json(self.sender_queue_path, queue)


    async def run(self):
        """The main, endless loop for the sender process."""
        print("Message Sender process started...")
        while True:
            try:
                # Atomically read and update the queue file
                sender_queue = utils.load_json(self.sender_queue_path)
                
                if sender_queue:
                    queued_item = sender_queue.pop(0)
                    utils.save_json(self.sender_queue_path, sender_queue)

                    telegram_user = queued_item.get("telegram_user")
                    client_to_use = self.clients.get(telegram_user)
                    
                    if not client_to_use:
                        print(f"Sender: User '{telegram_user}' not found or not specified. Picking a random client.")
                        # Ensure we don't try to get a .values() from an empty dict
                        if not self.clients:
                            print("CRITICAL: No clients available to send message.")
                            continue
                        client_to_use = random.choice(list(self.clients.values()))
                    
                    await self._send_message(client_to_use, queued_item)
                    
                    delay = random.uniform(
                        float(self.config.get('min_send_delay_secs', 30.0)),
                        float(self.config.get('max_send_delay_secs', 90.0))
                    )
                    print(f"Sender: Waiting {delay:.1f} seconds before checking queue again...")
                    await asyncio.sleep(delay)
                else:
                    # If the queue is empty, wait a shorter time before checking again.
                    await asyncio.sleep(10)
            
            except Exception as e:
                print(f"Sender: CRITICAL ERROR in sender loop: {e}")
                # Wait longer after a critical error to prevent rapid failure loops.
                await asyncio.sleep(60)

if __name__ == "__main__":
    sender = MessageSender()
    asyncio.run(sender.run())