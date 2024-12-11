import random
import json
from llm_personas import get_persona_type
import numpy as np
from datetime import datetime
from utils import * 
from openai_chat import get_llm_response
from telegram_scanner import send_to_telegram
import os

with open('prompt.json', 'r') as json_file:
    personas = json.load(json_file)

with open('personas.json', 'r') as json_file:
    personas_index = json.load(json_file)
    
with open('config.json', 'r') as json_file:
    config = json.load(json_file)

def conversation_to_topic(llm, chat, topic_model):    
    message = personas['generate_topic'] + '"' + chat + '"'
    topic_reply = llm.invoke(message)
    topic, prob = topic_model.transform(topic_reply)
    topics = topic_model.topic_labels_[topic[0]].split('_')[1:]
    topic_selected = topics[random.randint(0, len(topics) - 1)]
    
    return topic_selected

def check_initiation_send_status():
    conversation_list = load_list(config['data_dir'] + 'discussion.txt')
    
    if len(conversation_list) != 0:
        return True
    else:
        return False


def get_topic_list(llm, topic_model):
    previous_chat = get_chat() #extract previous 30 days chat
    topic = conversation_to_topic(llm, previous_chat, topic_model)
    
def read_topic_list(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data_list = [line.strip() for line in file]  # Read lines and strip whitespace
        return data_list
    except FileNotFoundError:
        print(f"The file {file_path} was not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    
def get_persona_question(conversations_dict):
    dict_keys = conversations_dict.keys()
    while True:
        random_persona = personas_index[str(random.randint(0, 9))]
        if random_persona not in dict_keys:
            break
    
    return random_persona

def divide_list_by_timeframes(input_list):
    if not input_list:
        raise ValueError("The input list must not be empty.")

    # Define the percentage distribution and corresponding timeframes
    percentages = [0.5, 0.3, 0.2]
    timeframes = [(5, 720), (720, 1080), (1080, 1440)]

    # Calculate the distribution of items across timeframes
    total_items = len(input_list)
    num_items = [round(total_items * p) for p in percentages]

    # Adjust the numbers to ensure the total equals the length of the list
    while sum(num_items) > total_items:
        num_items[0] -= 1
    while sum(num_items) < total_items:
        num_items[0] += 1

    # Assign items to timeframes
    result = {}
    index = 0
    for i, count in enumerate(num_items):
        for _ in range(count):
            result[input_list[index]] = timeframes[i]
            index += 1

    return result

def generate_random_boolean():
    return random.choice([True, False])
    

def get_bot_conversation(topic, sim_model):
    conversations_dict = {}
    
    persona = get_persona_type(topic, sim_model)
    persona_template = personas[persona]
    message = persona_template + ". people are discussion about " + topic + f"What do you think about it. Write a response within 20 words to it with emojis and don't tell you are {persona}."
    persona_reply = get_llm_response(message)
    
    time = random.randint(5, 60)
    conversations_dict[persona] = {time : persona_reply}
    
    number_of_bot_involved = random.randint(2, 10)
    bot_index = np.random.randint(0, 10, size=number_of_bot_involved)
    bot_index = list(set(bot_index))
    first_bot_index = next(key for key, value in personas_index.items() if value == persona)
    
    timeframe_dict = divide_list_by_timeframes(bot_index)
    
    for index in bot_index:
        print(index, " generating conversation...")
        if index == int(first_bot_index):
            continue
        
        persona = personas_index[str(index)]
        
        random_number_words = random.randint(20, 50)
        if generate_random_boolean():
            emoji_text = "with emoji"
        else:
            emoji_text = "without emoji"
        
        persona_template = personas[persona]
        message = persona_template + ". people are discussion about " + topic + f"What do you think about it. Write a response within {random_number_words} words to it {emoji_text} and don't tell you are {persona}."
        persona_reply = get_llm_response(message)
        timeframe = timeframe_dict[index]
        time = random.randint(timeframe[0], timeframe[1])

        conversations_dict[persona] = {time : persona_reply}
    
    return conversations_dict

def load_topic_db(key_value_status):
    discussed_topic_json_filename = config['data_dir'] + 'discussed_topic.json'
    
    if not os.path.exists(discussed_topic_json_filename):
        discussed_topic = {}
        save_dictionary(discussed_topic, discussed_topic_json_filename)
    
    with open(config['data_dir'] + 'discussed_topic.json', 'r') as json_file:
        discussed_topic = json.load(json_file)
    
    if key_value_status == False:
        discussed_topic = list(discussed_topic.values())
    
    return discussed_topic

def get_topic_status(topic):
    discussed_topic = load_topic_db(False)
    
    if topic not in discussed_topic:
        return True
        
    else:
        return False
    
def save_topic_to_db(topic):
    discussed_topic = load_topic_db(True)
    current_timestamp = datetime.now()
    
    discussed_topic[str(current_timestamp)] = topic
    
    with open(config['data_dir'] + 'discussed_topic.json', 'w', encoding='utf-8') as json_file:
        json.dump(discussed_topic, json_file, indent=4)  # Use indent for pretty
    
    print(f'saved {topic} to the discussed topic successfully')


def random_conversation_timestamp():
    current_time = datetime.now()
    random_timestamps = []

    for _ in range(5):
        if not random_timestamps:
            # First timestamp
            random_timestamps.append(current_time)
        else:
            # Add at least 16 hours (18000 seconds) to the last timestamp
            min_gap = random_timestamps[-1] + timedelta(hours=16)
            random_seconds = random.randint(0, 3600)  # Add up to an extra hour for randomness
            next_timestamp = min_gap + timedelta(seconds=random_seconds)
            random_timestamps.append(next_timestamp)
    
    # Format the timestamps as strings
    formatted_timestamps = [ts.strftime("%Y-%m-%d %H") for ts in random_timestamps]
    
    return formatted_timestamps


def send_random_talks():
    directory = config['data_dir']
    filename = 'random_conversation_time.txt'
    file_path = os.path.join(directory, filename)
    
    if not os.path.exists(file_path):
        random_conversation_time_list = random_conversation_timestamp()
        save_list(random_conversation_time_list, file_path)
    
    else:
        random_conversation_time_list = load_list(file_path)
        
        if len(random_conversation_time_list) == 0:
            random_conversation_time_list = random_conversation_timestamp()
            save_list(random_conversation_time_list, file_path)
            
        else:
            random_conversation_time_list = load_list(file_path)
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H")
            
            random_content_dict = {
                "1": "greetings",
                "2":"queries",
                "3":"discussion topic"
                }
            
            random_content = random_content_dict[str(random.randint(1, 3))]
            
            for random_conv_time in random_conversation_time_list:
                if random_conv_time == current_time:
                    if random_content == "greetings":
                        content = "Imagine you're greeting a friend in a group. Write a warm and friendly message. Keep it short wihin 10 words"
                    
                    else:
                        content = "You are a human who have crypto, web3, and AI knowledge. Compose a thought-provoking message that could be either the future of web3, blockchain, AI, issues related with it, or question related to it. Keep it short within 20-40 words"

                    reply = get_llm_response(content)
                    # print(f"random conversation {reply} sent to telegram")
                    send_to_telegram("random_topic", reply)
                    random_conversation_time_list.remove(random_conv_time)
                    save_list(random_conversation_time_list, file_path)
                    
                

    
    









    