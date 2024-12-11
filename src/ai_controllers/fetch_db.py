#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 28 21:18:29 2024

@author: krishnayadav
"""

from google.cloud.firestore import Query
import datetime



def get_last_100_message(collection_name, db):
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    # Fetch the last 100 messages based on the 'date' field
    data_list = []
    docs = (
        collection_ref.order_by("date", direction=Query.DESCENDING)
        .limit(100)
        .stream()
    )
    
    for doc in docs:
        doc_data = doc.to_dict()  # Convert the document snapshot to a dictionary
        data_list.append(doc_data)  # Append the data to the list
    
    # Extract the 'text' field from the last 100 messages
    message_list = [doc['text'] for doc in data_list if 'text' in doc]
    
    return message_list


def get_last_message(collection_name, db):
    # Sanitize the collection name
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    # Fetch the last 10 messages based on the 'date' field
    data_list = []
    docs = (
        collection_ref.order_by("date", direction=Query.DESCENDING)
        .limit(1)
        .stream()
    )
    
    for doc in docs:
        doc_data = doc.to_dict()  # Convert the document snapshot to a dictionary
        data_list.append(doc_data)  # Append the data to the list
    
    # Create a dictionary with 'date' as keys and 'text' as values
    message_list = {
        doc['date']: {'text': doc['text'], 'sender_id': doc['sender_id']}
        for doc in data_list
        if 'date' in doc and 'text' in doc and 'sender_id' in doc
    }
    

    return message_list

