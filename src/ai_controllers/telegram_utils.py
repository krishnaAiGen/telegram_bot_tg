import asyncio
import random
import time
import json
from telethon import TelegramClient
from utils import load_list, save_list  # Assuming this is imported correctly
import os

USERS = {    
    "JoiN9911": {
        "api_id": 23724256,
        "api_hash": "e9e6694fcaa2b502c2d2bbae922e4414",
        "username": "JoiN9911",
        "phone_no": "+916299207265"
    },
    
    "davethm": {
        "api_id": 29185654,
        "api_hash": "b76874a78a10950b85045e9ef94cae39",
        "username": "davethm",
        "phone_no": "+2348109475171"
    },
    
    "devtoye": {
        "api_id": 11150975,
        "api_hash": "b954ee33b49fc823e024347c6bf3647e",
        "username": "devtoye",
        "phone_no": "+2347044735660"
    }
}

# Load config
with open('config.json', 'r') as json_file:
    config = json.load(json_file)

# Create clients
clients = {user: TelegramClient(user, user_config["api_id"], user_config["api_hash"])
           for user, user_config in USERS.items()}

async def send_message_from_user(user, channel_username, message):
    if user not in clients:
        print(f"User {user} not found!")
        return
    
    client = clients[user]
    async with client:
        try:
            await client.send_message(channel_username, message)
            print(f"Message sent to {channel_username} by {user}: {message}")
        except Exception as e:
            print(f"Error sending message: {e}")

async def create_session(users):
    for user in users.keys():
        print(f"******{user}******")
        channel_username = '@' + config['destination_channel']
        message = "Hello"
        # await send_message_from_user(user, channel_username, message)
        print(f"Session for {user} created!!")

def get_random_username():
    return random.choice(list(USERS.keys()))

def load_list1(file_name):
    with open(file_name, 'r') as file:
        polkassembly_message = json.load(file)
    
    return polkassembly_message

def save_list1(polkassembly_message, file_name):
    with open(file_name, 'w') as file:
        json.dump(polkassembly_message, file)

def get_message():
    telegram_message = load_list1(config['data_dir'] + 'polkassembly_message.txt')
    return telegram_message[0] if telegram_message else ""

def delete_message():
    telegram_message = load_list1(config['data_dir'] + 'polkassembly_message.txt')
    if telegram_message:
        del telegram_message[0]

    save_list1(telegram_message, config['data_dir'] + 'polkassembly_message.txt')

async def send_main():
    # Create initial sessions
    await create_session(USERS)
    
    while True:
        try:
            channel_username = '@' + config['destination_channel']
            user = get_random_username()
            
            if not os.path.exists(config['data_dir'] + 'polkassembly_message.txt'):
                continue
            
            message = get_message()
            
            if message!= "":     
                await send_message_from_user(user, channel_username, message)
                delete_message()
            
            await asyncio.sleep(60)  # Use asyncio.sleep for async functions
        except Exception as e:
            print(f"Error in main loop: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(send_main())