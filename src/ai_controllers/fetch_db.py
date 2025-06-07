# fetch_db.py
from google.cloud.firestore import Query
import datetime

async def get_last_message(collection_name, db):
    """Asynchronously fetches the single last message from a collection."""
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    docs_stream = collection_ref.order_by("date", direction=Query.DESCENDING).limit(1).stream()
    
    messages = [doc.to_dict() async for doc in docs_stream]
    
    if not messages:
        return None
        
    last_message = messages[0]
    
    if isinstance(last_message.get('date'), datetime.datetime):
         last_message['date'] = last_message['date'].replace(tzinfo=datetime.timezone.utc)
    
    return last_message

async def get_last_100_message_texts(collection_name, db):
    """Asynchronously fetches the text of the last 100 messages."""
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    docs_stream = (
        collection_ref.order_by("date", direction=Query.DESCENDING)
        .limit(100)
        .stream()
    )
    
    message_texts = [
        doc.to_dict().get('text', '') async for doc in docs_stream if 'text' in doc.to_dict()
    ]
    return message_texts