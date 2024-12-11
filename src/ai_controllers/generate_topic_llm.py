#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 13:09:24 2024

@author: krishnayadav
"""

from fetch_db import *
import re
from openai_chat import get_llm_response
import json

# Load config
with open('config.json', 'r') as json_file:
    config = json.load(json_file)

def get_topic_llm(db):
    chat_messages = get_last_100_message(config['source_channel'], db)
    chat_messages = [msg for msg in chat_messages if len(msg.split()) > 2]
    chat_messages_join = ''.join(chat_messages)
    
    content  = f"""
    #     Topic: "{chat_messages_join}"
    #     Extract two numbered list of key topics discussed from above chat with some description. Each topic should be concise and directly relevant.
    #     """
    
    topics = []
    while len(topics) <= 0: 
            print("iteration...")
            response = get_llm_response(content)
            topics = re.findall(r'\d+\.\s*(.*)', response)    
            
    return topics
    
    
    
    