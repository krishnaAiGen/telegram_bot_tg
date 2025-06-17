# src/services/fetch_db.py
import asyncio
import datetime
from google.cloud.firestore import Query

def _get_docs_sync(query):
    """A synchronous helper function to execute a Firestore query and get results."""
    return [doc.to_dict() for doc in query.stream()]

async def get_last_message(collection_name: str, db) -> dict | None:
    """
    Asynchronously fetches the single most recent message from a Firestore collection.
    """
    # Use the single channel config if it exists
    final_name = f"conversation_ai_{collection_name}"
    collection_ref = db.collection(final_name)
    
    query = collection_ref.order_by("date", direction=Query.DESCENDING).limit(1)
    
    # --- CORRECTED LINE ---
    # Run the synchronous database call in a background thread
    messages = await asyncio.to_thread(_get_docs_sync, query)
    
    if not messages:
        return None
        
    last_message = messages[0]
    
    if isinstance(last_message.get('date'), datetime.datetime):
         last_message['date'] = last_message['date'].replace(tzinfo=datetime.timezone.utc)
    
    return last_message

async def get_last_100_message_texts(collection_name: str, db) -> list[str]:
    """
    Asynchronously fetches the text content of the last 100 messages.
    """
    final_name = f"conversation_ai_{collection_name}"
    collection_ref = db.collection(final_name)
    
    query = collection_ref.order_by("date", direction=Query.DESCENDING).limit(100)
    
    # --- CORRECTED LINE ---
    # Run the synchronous database call in a background thread
    docs = await asyncio.to_thread(_get_docs_sync, query)
    
    message_texts = [
        doc.get('text', '') for doc in docs if 'text' in doc
    ]
    return message_texts