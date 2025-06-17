# src/services/slack_bot.py
import aiohttp
from config.settings import APP_CONFIG

WEBHOOK_URL = APP_CONFIG.get('slack_webhook_url')

async def post_to_slack(message: dict):
    """
    Asynchronously posts a dictionary as a formatted message to Slack.
    This function is preserved from the original codebase for potential use.
    """

    # If no webhook is configured in the .env file, do nothing.
    if not WEBHOOK_URL:
        return

    # Preserves the original formatting logic.
    formatted_message = "\n".join([f"{key}: {value}" for key, value in message.items()])
    payload = { "text": formatted_message }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WEBHOOK_URL, json=payload, timeout=10) as response:
                if response.status != 200:
                    print(f"Failed to post generic message to Slack: {response.status}")
        except Exception as e:
            print(f"Error posting generic message to Slack: {e}")

async def post_error_to_slack(error_message: str):
    """Asynchronously posts a formatted error traceback to a Slack channel."""
    if not WEBHOOK_URL:
        print("Slack webhook URL not configured. Cannot post error alert.")
        return
        
    # Uses Slack's "Blocks" format for a much richer and more readable error message.
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Error in Conversational Bot"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "An unhandled exception occurred in one of the application processes."
                }
            },
            {
			    "type": "divider"
		    },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    # To avoid hitting Slack's message limits, we send only the last 2500 characters.
                    "text": f"```\n{error_message[-2500:]}\n```"
                }
            }
        ]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WEBHOOK_URL, json=payload, timeout=10) as response:
                 if response.status != 200:
                    print(f"Failed to post error alert to Slack: {response.status}")
        except Exception as e:
            print(f"Error posting to Slack: {e}")