# slack_bot.py
import json
import aiohttp

# Load configuration once when the module is imported
with open('config.json', 'r') as json_file:
    config = json.load(json_file)

WEBHOOK_URL = config.get('webhook_url')

# This function is preserved and refactored to be asynchronous as per your instructions.
async def post_to_slack(message: dict):
    """Asynchronously posts a dictionary as a formatted message to Slack."""
    if not WEBHOOK_URL:
        print("Slack webhook URL not configured. Skipping notification.")
        return

    # The original formatting logic is preserved.
    formatted_message = "\n".join([f"{key}: {value}" for key, value in message.items()])
    
    payload = { "text": formatted_message }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WEBHOOK_URL, json=payload) as response:
                if response.status == 200:
                    print("Generic message posted successfully to Slack.")
                else:
                    print(f"Failed to post generic message: {response.status}, {await response.text()}")
        except aiohttp.ClientError as e:
            print(f"Error posting generic message to Slack: {e}")

async def post_error_to_slack(error_message: str):
    """Asynchronously posts a formatted error message to a Slack channel."""
    if not WEBHOOK_URL:
        print("Slack webhook URL not configured. Skipping notification.")
        return
        
    # Formatting the message for better readability in Slack
    payload = {"text": f"🚨 **Error in Telegram Bot** 🚨\n```\n{error_message}\n```"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WEBHOOK_URL, json=payload) as response:
                if response.status == 200:
                    print("Error message posted successfully to Slack.")
                else:
                    print(f"Failed to post error to Slack: {response.status} {await response.text()}")
        except aiohttp.ClientError as e:
            print(f"Error posting to Slack: {e}")