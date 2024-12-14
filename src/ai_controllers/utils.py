import pickle
import json
from datetime import datetime, timedelta
import pickle
import os
from datetime import datetime
import pytz

with open('config.json', 'r') as json_file:
    config = json.load(json_file)

def save_dictionary(dictionary, filename):        
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(dictionary, json_file, indent=4)  # Use indent for pretty

def load_dictionary(filename):
    with open(filename, 'r', encoding='utf-8') as json_file:
        return json.load(json_file)

def save_list(lst, filename):
    with open(filename, 'wb') as file:
        pickle.dump(lst, file)

def load_list(filename):
    # filename = filename + 'discussion.txt'
    with open(filename, 'rb') as file:
        return pickle.load(file)


def store_initiate_conversation(conversations_dict):
    time_persona_dict = {}
    description_list = []
    now = datetime.now()
    # current_time = now.strftime("%H:%M")

    for key, value in conversations_dict.items():
        temp_list = []
        for key1, value1 in value.items():

            new_time = now + timedelta(minutes=key1)
            new_time_str = new_time.strftime("%Y-%m-%d %H")
            temp_list.append(key)
            temp_list.append(value1)
            time_persona_dict[new_time_str] = temp_list
            description_list.append(value1)
            
            now = new_time
    
    save_dictionary(time_persona_dict, config['data_dir'] + 'time_persona.json')
    # save_list(description_list, config['data_dir'] + 'discussion.txt')

    print("Initiate conversation data saved successfully!")
    
def get_ist_time():
    ist_timezone = pytz.timezone('Asia/Kolkata')    
    current_utc_time = datetime.now(pytz.utc)
    
    current_ist_time = current_utc_time.astimezone(ist_timezone)    
    ist_time_string = current_ist_time.strftime('%Y-%m-%d %H:%M:%S')
    
    return ist_time_string

def save_error(error):
    error_filename = config['data_dir'] + 'error.json'
    current_time = get_ist_time()
    
    if not os.path.exists(error_filename):
        error_dict = {}
        error_dict[current_time] = error
        save_dictionary(error_dict, error_filename)
    
    else:
        error_dict = load_dictionary(error_filename)
        error_dict[current_time] = error
        save_dictionary(error_dict, error_filename)
        
    print(f"error {error} saved")
        
    
            
    


    
