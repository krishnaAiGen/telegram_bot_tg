#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 13 20:09:24 2024

@author: krishnayadav
"""

import requests
import json

# Load configuration from the config.json file
with open('config.json', 'r') as json_file:
    config = json.load(json_file)

# Extract webhook URL from config
webhook_url = config['webhook_url']

def post_to_slack(message):
      # Convert message dictionary to a string with each key-value on a new line
    formatted_message = "\n".join([f"{key}: {value}" for key, value in message.items()])
    
    # Create the payload to send to Slack
    payload = {
        "text": formatted_message  # Message to send to Slack
    }
    
    try:
        # Send a POST request to the Slack webhook URL
        response = requests.post(webhook_url, json=payload)
    
        # Check if the request was successful
        if response.status_code == 200:
            print("Message posted successfully")
        else:
            print(f"Failed to post message: {response.status_code}, {response.text}")
    
    except Exception as e:
        print(f"Error posting message: {e}")
        
def post_error_to_slack(error_message):
    payload = {
        "text": error_message  # Message to send to Slack
    }
    
    try:
        # Send a POST request to the Slack webhook URL
        response = requests.post(webhook_url, json=payload)
    
        # Check if the request was successful
        if response.status_code == 200:
            print("Message posted successfully")
        else:
            print(f"Failed to post message: {response.status_code}, {response.text}")
    
    except Exception as e:
        print(f"Error posting message: {e}")
        