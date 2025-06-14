# src/ai_controllers/slack_bot.py
import aiohttp
from config import APP_CONFIG

WEBHOOK_URL = APP_CONFIG.get('slack_webhook_url')

async def post_to_slack(message: dict):
    """
    Asynchronously posts a dictionary as a formatted message to Slack.
    This function is preserved from the original codebase.
    """
    if not WEBHOOK_URL:
        # Silently fail if no webhook is configured
        return

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
    """Asynchronously posts a formatted error message to a Slack channel."""
    if not WEBHOOK_URL:
        print("Slack webhook URL not configured. Cannot post error.")
        return
        
    # Uses Slack's "blocks" for better formatting of error messages
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
                    "text": "An exception occurred in one of the application processes."
                }
            },
            {
			    "type": "divider"
		    },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```\n{error_message[-2500:]}\n```" # Show last 2500 chars of traceback
                }
            }
        ]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WEBHOOK_URL, json=payload, timeout=10) as response:
                 if response.status != 200:
                    print(f"Failed to post error to Slack: {response.status}")
        except Exception as e:
            print(f"Error posting to Slack: {e}")