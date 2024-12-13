import os
import json
from fetch_db import * 
from utils import *
from datetime import datetime, timedelta
from utils import *
import pytz  
from telegram_utils import save_list1, load_list1
import random



LAST_MESSAGE_DATE = 0


with open('config.json', 'r') as json_file:
    config = json.load(json_file)

def send_to_telegram(message_type, reply):       
    record_conversation_filename = config['data_dir'] + 'record_conversation.json'
    
    if not os.path.exists(record_conversation_filename):
        record_conversation = {}
        record_conversation[message_type] = reply
        save_dictionary(record_conversation, record_conversation_filename)
    
    else:
        record_conversation = load_dictionary(record_conversation_filename)
        ist_time = get_ist_time()
        record_conversation[ist_time] = message_type + '----' + reply
        save_dictionary(record_conversation, record_conversation_filename)
    
    file_name = config['data_dir'] + 'polkassembly_message.txt'
    polkassembly_message = []
    
    if not os.path.exists(file_name):
        polkassembly_message.append(reply)
    
        with open(file_name, 'w') as file:
            json.dump(polkassembly_message, file)
            
    else:
        polkassembly_message = load_list1(config['data_dir'] + 'polkassembly_message.txt')
        polkassembly_message.append(reply)
        save_list1(polkassembly_message, config['data_dir'] + 'polkassembly_message.txt')
        print(f"message {reply} was saved to polkassembly_message")


def clean_bots(chat_messages):
    clean_bot_filename = config['data_dir'] + 'clean_bot.json'
    if not os.path.exists(clean_bot_filename):
        clean_bot = {}
        clean_bot['counter'] = 10
        save_dictionary(clean_bot, clean_bot_filename)
    
    else:
        clean_bot = load_dictionary(clean_bot_filename)
        clean_bot_number = clean_bot['counter']
        if clean_bot_number == 0:
            clean_bot_number = 10
        
        else:
            clean_bot_number = clean_bot_number - 1 
        
        clean_bot['counter'] = clean_bot_number
        save_dictionary(dictionary, filename)
            
    if clean_bot_number in [2,4,6,8,9]:
        bot_id_list = [7347516532, 7235202962, 7661414514]
        keys_to_delete = [key for key, value in chat_messages.items() if value['sender_id'] in bot_id_list]
        for key in keys_to_delete:
            del chat_messages[key]
    
    return chat_messages

def conversation_initiate_status(db):
    global LAST_MESSAGE_DATE
    
    current_time = get_ist_time()
    current_time = datetime.fromisoformat(current_time)
    
    inititate_status = False
    react_status = False
    reaction_string = ''
    reacted_to = ''
    
    chat_messages1 = get_last_message(config['source_channel'], db)
    LAST_MESSAGE_DATE = next(iter(chat_messages1)).strftime('%Y-%m-%d %H:%M:%S')
    chat_messages1 = clean_bots(chat_messages1)
    
    #changing the UTC time to 5:30 hrs backward
    chat_messages = {}
    for key, value in chat_messages1.items(): 
        new_time = key + timedelta(hours=5, minutes=30)
        
        chat_messages[new_time] = value
        
    
    if len(chat_messages) == 0:
        react_status = False
        reaction_string = ''
        reacted_to = ''
        
        initiate_treshold_date = datetime.fromisoformat(LAST_MESSAGE_DATE) + timedelta(hours = random.randint(2, 5))
        """
        This logic checks whether to initiate chat or not.
        """
        if current_time > initiate_treshold_date:
            discussion_list = load_list(config['data_dir'] + 'discussion.txt')
            if len(discussion_list) == 0:
                inititate_status = True
            
            else:
                inititate_status = False
                     
        return react_status, reaction_string, reacted_to, inititate_status, LAST_MESSAGE_DATE
    
    else:            
        """
        This logic is for checking whether to react or not
        """
        react_treshold_date = datetime.fromisoformat(LAST_MESSAGE_DATE) + timedelta(hours = random.randint(1, 3))
        initiate_treshold_date = datetime.fromisoformat(LAST_MESSAGE_DATE) + timedelta(hours = random.randint(2, 5))
            
        if current_time > react_treshold_date:       
            react_status = True
            
            reaction_string = chat_messages[next(iter(chat_messages))]['text']
            reacted_to = chat_messages[next(iter(chat_messages))]['sender_id']
                
        
        """
        This logic checks whether to initiate chat or not.
        """
        if current_time > initiate_treshold_date:
            discussion_list = load_list(config['data_dir'] + 'discussion.txt')
            if len(discussion_list) == 0:
                inititate_status = True
            
            else:
                inititate_status = False
        
        
        return react_status, reaction_string, reacted_to, inititate_status, LAST_MESSAGE_DATE
    

def create_db(directory, filename="discussed_topic.json"):
    # Construct the full path to the file
    file_path = os.path.join(directory, filename)

    # Check if the file exists
    if not os.path.exists(file_path):
        # Create the file with an empty dictionary
        with open(file_path, 'w') as file:
            file.write('{}')  # Creates an empty JSON dictionary
        print(f"File '{filename}' created in '{directory}'.")
    
    if not os.path.exists(config['data_dir'] + 'discussion.txt'):
        file_name = config['data_dir'] + 'discussion.txt'
        empty_list = []

        with open(file_name, 'wb') as file:
            pickle.dump(empty_list, file)
    
    else:
        print(f"File '{filename}' already exists in '{directory}'.")

def send_initiation_chat():
    time_persona_dict = load_dictionary(config['data_dir'] + 'time_persona.json')
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H")
    
    
    if len(time_persona_dict) == 0:
        return 
    
    else:
        counter = 0
        for key, value in time_persona_dict.items():
            if key == current_time:
                discussion_list = load_list(config['data_dir'] + 'discussion.txt')
                send_to_telegram("initiation", value)
                del time_persona_dict[key]
                discussion_list.pop(counter)
                
                save_dictionary(time_persona_dict, config['data_dir'] + 'time_persona.json')
                save_list(discussion_list, config['data_dir'] + 'discussion.txt')

            counter = counter + 1
        
        


    