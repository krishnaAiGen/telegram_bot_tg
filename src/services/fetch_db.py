# src/services/fetch_db.py
from google.cloud.firestore import Query
import datetime

async def get_last_message(collection_name: str, db) -> dict | None:
    """
    Asynchronously fetches the single most recent message from a Firestore collection,
    ordered by the 'date' field.

    Args:
        collection_name (str): The base name of the channel (e.g., 'my_channel').
        db: An initialized Firestore database client instance.

    Returns:
        The message data as a dictionary, or None if the collection is empty.
    """
    # Sanitize the name to create the final collection ID, preserving original logic.
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    # Construct the query to get 1 document, ordered by date descending.
    # The .stream() method creates an asynchronous iterator.
    docs_stream = collection_ref.order_by("date", direction=Query.DESCENDING).limit(1).stream()
    
    # Use the 'async for' syntax to iterate over the asynchronous results.
    messages = [doc.to_dict() async for doc in docs_stream]
    
    if not messages:
        return None
        
    last_message = messages[0]
    
    # CRITICAL FIX: Ensure the datetime object from Firestore is timezone-aware (UTC).
    # This prevents crashes when comparing it with timezone-aware datetimes from elsewhere.
    if isinstance(last_message.get('date'), datetime.datetime):
         last_message['date'] = last_message['date'].replace(tzinfo=datetime.timezone.utc)
    
    return last_message

async def get_last_100_message_texts(collection_name: str, db) -> list[str]:
    """
    Asynchronously fetches the text content of the last 100 messages.
    This is used to provide historical context for generating new conversation topics.

    Args:
        collection_name (str): The base name of the channel.
        db: An initialized Firestore database client instance.

    Returns:
        A list of strings, where each string is the text of a message.
    """
    sanitized_name = collection_name.lstrip('@')
    final_name = f"conversation_ai_{sanitized_name}"
    collection_ref = db.collection(final_name)
    
    # Query for the last 100 documents ordered by date.
    docs_stream = (
        collection_ref.order_by("date", direction=Query.DESCENDING)
        .limit(100)
        .stream()
    )
    
    # Use a concise and efficient list comprehension with 'async for' to extract
    # the 'text' field from each document, with a fallback to an empty string.
    message_texts = [
        doc.to_dict().get('text', '') async for doc in docs_stream if 'text' in doc.to_dict()
    ]
    return message_texts