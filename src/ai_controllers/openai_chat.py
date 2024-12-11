#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 28 17:58:40 2024

@author: krishnayadav
"""

import requests
import json

with open('config.json', 'r') as json_file:
    config = json.load(json_file)

def get_llm_response(content):
    api_key = config["openai_api_key"]
    # Set up the headers for the request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Define the payload for the API request
    payload = {
        "model": "gpt-4",  # Specify the model you want to use
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": content}
        ],
        "max_tokens": 150  # Limit the response length
    }
    
    # Send a POST request to the OpenAI API
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    return response.json()['choices'][0]['message']['content']


