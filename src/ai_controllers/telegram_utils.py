# telegram_utils.py
import asyncio
import random
import json
from telethon import TelegramClient
from utils import StateManager # IMPORTING the unified StateManager

class MessageSender:
    """
    A standalone process that reads messages from the central queue (managed by StateManager)
    and sends them to Telegram using a random user account.
    """
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Preserving the original USERS dictionary
        self.users = {    
            "JoiN9911": {"api_id": 23724256, "api_hash": "e9e6694fcaa2b502c2d2bbae922e4414"},
            "davethm": {"api_id": 29185654, "api_hash": "b76874a78a10950b85045e9ef94cae39"},
            "devtoye": {"api_id": 11150975, "api_hash": "b954ee33b49fc823e024347c6bf3647e"}
        }
        self.destination_channel = '@' + self.config['destination_channel']
        
        # CRITICAL CHANGE: Using the central StateManager for the queue
        self.state_manager = StateManager(self.config['data_dir'])
        
        self.clients = {
            user: TelegramClient(user, config["api_id"], config["api_hash"])
            for user, config in self.users.items()
        }
        self.client_list = list(self.clients.values())
        print(f"Initialized {len(self.client_list)} sender accounts.")

    async def _send_message(self, client: TelegramClient, message: str):
        """Connects a client and sends a message, with human-like typing action."""
        try:
            async with client:
                print(f"Sending message via {client.session.filename}...")
                async with client.action(self.destination_channel, 'typing'):
                    await asyncio.sleep(random.uniform(3, 7))
                await client.send_message(self.destination_channel, message)
            print(f"Message sent successfully: '{message[:50]}...'")
        except Exception as e:
            print(f"Error sending message with {client.session.filename}: {e}")
            # Re-queue the message to be retried
            self.state_manager.add_message_to_queue(message)
            print("Message re-queued for a later attempt.")

    async def run(self):
        """The main, endless loop for the sender process."""
        print("Message Sender starting...")
        while True:
            try:
                # UNIFIED LOGIC: Get message from the central queue
                message = self.state_manager.get_message_from_queue()
                
                if message:
                    random_client = random.choice(self.client_list)
                    await self._send_message(random_client, message)
                    
                    delay = random.uniform(
                        self.config.get('min_send_delay_secs', 60),
                        self.config.get('max_send_delay_secs', 180)
                    )
                    print(f"Waiting {delay:.1f} seconds before checking queue again...")
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(20)
            
            except Exception as e:
                print(f"CRITICAL ERROR in sender loop: {e}")
                await asyncio.sleep(60)

if __name__ == "__main__":
    sender = MessageSender()
    asyncio.run(sender.run())