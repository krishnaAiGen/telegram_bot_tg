# src/ai_controllers/fetch_db.py
from google.cloud.firestore import Query
import datetime

async def get_last_message(collection_name: str, db) -> dict | None:
    """
    Asynchronously fetches the single most recent message from a Firestore collection.
    Returns the message data as a dictionary, or None if the collection is empty.
    """
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    # Create an asynchronous stream to get the last document
    docs_stream = collection_ref.order_by("date", direction=Query.DESCENDING).limit(1).stream()
    
    # Use async for to iterate over the stream's results
    messages = [doc.to_dict() async for doc in docs_stream]
    
    if not messages:
        return None
        
    last_message = messages[0]
    
    # This is a critical fix to ensure the datetime object is timezone-aware (UTC),
    # which prevents errors when comparing it to other timezone-aware datetimes.
    if isinstance(last_message.get('date'), datetime.datetime):
         last_message['date'] = last_message['date'].replace(tzinfo=datetime.timezone.utc)
    
    return last_message

async def get_last_100_message_texts(collection_name: str, db) -> list[str]:
    """
    Asynchronously fetches the text content of the last 100 messages.
    This is used to provide context for generating new conversation topics.
    """
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    docs_stream = (
        collection_ref.order_by("date", direction=Query.DESCENDING)
        .limit(100)
        .stream()
    )
    
    # A concise list comprehension to extract the 'text' from each document
    message_texts = [
        doc.to_dict().get('text', '') async for doc in docs_stream if 'text' in doc.to_dict()
    ]
    return message_texts