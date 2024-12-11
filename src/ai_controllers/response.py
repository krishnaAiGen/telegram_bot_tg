#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 21 20:30:13 2024

@author: krishnayadav
"""

from sentence_transformers import SentenceTransformer, util
from llm_personas import get_human_reply, get_crypto_reply, get_persona_type, refine_reply
from classify_chat import ClassifyChat
from langchain_community.llms import Ollama
import time
from telegram_scanner import *
from initiate_topic import *
import json
import random
from generate_topic_llm import *
from utils import * 
import firebase_admin
from firebase_admin import credentials, firestore
from openai_chat import * 
# from telegram_utils import send_main


with open('config.json', 'r') as json_file:
    config = json.load(json_file)
    
with open('prompt.json', 'r') as json_file:
    personas = json.load(json_file)

    
cred = credentials.Certificate(config["firebase_cred"])
app = firebase_admin.initialize_app(cred)
db = firestore.client()

def telegram_react(reaction_string, sim_model):
    message_type, human_crypto_score = classify_human_blockchain.predict(reaction_string)
    if message_type == 'human':
        content = "you are a human being. reply to this message and don't reply messages so that you can be revealed as bot': " + reaction_string
        human_reply = get_llm_response(content)
        
        return human_reply
    else:
        persona = get_persona_type(reaction_string, sim_model)
        content = personas[persona] + " reply to this message: " + reaction_string
        
        crypto_reply = get_llm_response(content)
        
        return crypto_reply

def initiate_bot_conversation(sim_model):
    #get topic from crypto topic list 
    topic_list = get_topic_llm(db)
    topic = topic_list[0]
    topic_status = get_topic_status(topic)
    
    while not topic_status:
         topic_list = get_topic_llm(db)
         topic = topic_list[0]
         topic_status = get_topic_status(topic)
    
    #get topic from external hot topic
    save_topic_to_db(topic)
    
    conversations_dict = get_bot_conversation(topic, sim_model)
    sorted_conversations_dict = dict(sorted(conversations_dict.items(), key=lambda x: list(x[1].keys())[0]))

    
    store_initiate_conversation(sorted_conversations_dict)
    
    return sorted_conversations_dict

def close_firebase_client(app):
    firebase_admin.delete_app(app)
    print("Firebase client closed successfully.")
        


if __name__ == "__main__":
    global sim_model
    sim_model = SentenceTransformer('all-MiniLM-L6-v2')  # You can choose another model if preferred
    
    classify_human_blockchain = ClassifyChat(config['chat_classify'])
    create_db(config['data_dir'])
    
    # asyncio.run(main())
    # asyncio.run(send_main())
    
    while True:
        try:
            react_status, reaction_string, reacted_to, inititate_status = conversation_initiate_status(db)
            initiation_send_status = check_initiation_send_status()
            
            # inititate_status = True
            # initiation_send_status = True
            
            send_random_message_status = True
            
            if react_status:
                reply = telegram_react(reaction_string, sim_model)
                send_to_telegram("react", reply)
            
            if inititate_status:
                reply = initiate_bot_conversation(sim_model)  
            
            if initiation_send_status:
                send_initiation_chat()
            
            if send_random_message_status:
                send_random_talks()
            
            print("Next scan in 1:00")
            
        except Exception as e:
            print("--------error occured-------", e)
            save_error(e)
            continue
        
        time.sleep(60)
    
    close_firebase_client(app)

            
            







