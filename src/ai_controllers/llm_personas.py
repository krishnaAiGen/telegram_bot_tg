from sentence_transformers import util
import json
import re
import random

with open('prompt.json', 'r') as json_file:
    personas = json.load(json_file)

def get_persona_type(message, sim_model):
    # Compute embedding for the message
    message_embedding = sim_model.encode(message, convert_to_tensor=True)

    not_included_persona = ['Human', 'randomness', 'generate_topic']
    # # Compute embeddings for each persona and calculate similarity
    # similarities = {}
    # for persona, description in personas.items():
    #     if persona in not_included_persona:
    #         continue
    #     persona_embedding = sim_model.encode(description, convert_to_tensor=True)
    #     similarity = util.pytorch_cos_sim(message_embedding, persona_embedding).item()
    #     similarities[persona] = similarity

    # # Find the most relevant persona
    # most_relevant_persona = max(similarities, key=similarities.get)
    
    while True:
        key_persona = list(personas.keys())
        most_relevant_persona = key_persona[random.randint(0, 11)]
        if most_relevant_persona not in not_included_persona:
            break
    
    return most_relevant_persona
    
def get_human_reply(message, llm):
    # message = "So... airdrop of the token is still something on or not at all ?"
    message_length = len(message.split(' '))

    message = personas["Human"] + f' in {message_length} words. "' + message + '"'
    human_reply = llm.invoke(message)
    
    return human_reply
    

def get_crypto_reply(message, llm, persona):
    message = personas[persona] + personas["randomness"] +  message
    crypto_reply = llm.invoke(message)
    
    return crypto_reply

def refine_reply(message):
   # Remove newline characters
   response_text = message.replace('\n', ' ')
   
   # Remove any symbols or numbers, only keep alphabets and spaces
   cleaned_text = re.sub(r'[^a-zA-Z ]', '', response_text)
   
   # Remove extra spaces
   cleaned_text = re.sub(r' +', ' ', cleaned_text).strip()
   
   return cleaned_text
    

