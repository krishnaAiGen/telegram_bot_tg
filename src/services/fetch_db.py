import asyncio
import datetime
from google.cloud.firestore import Query

def save_message_to_db(collection_name: str, message, db):
    """Saves a Telethon message object to a Firestore collection."""
    if not message or not message.text:
        return
    
    collection_ref = db.collection(f"conversation_ai_{collection_name}")
    doc_ref = collection_ref.document(str(message.id))
    doc_data = {
        "message_id": message.id,
        "text": message.text,
        "sender_id": getattr(message.sender, 'id', None),
        "date": message.date
    }
    doc_ref.set(doc_data)
    print(f"[DB] Saved message ID {message.id} to Firestore.")

def _get_docs_sync(query):
    return [doc.to_dict() for doc in query.stream()]

async def get_last_message(collection_name: str, db) -> dict | None:
    collection_ref = db.collection(f"conversation_ai_{collection_name}")
    query = collection_ref.order_by("date", direction=Query.DESCENDING).limit(1)
    messages = await asyncio.to_thread(_get_docs_sync, query)
    if not messages: return None
    last_message = messages[0]
    if isinstance(last_message.get('date'), datetime.datetime):
         last_message['date'] = last_message['date'].replace(tzinfo=datetime.timezone.utc)
    return last_message

async def get_last_100_message_texts(collection_name: str, db) -> list[str]:
    collection_ref = db.collection(f"conversation_ai_{collection_name}")
    query = collection_ref.order_by("date", direction=Query.DESCENDING).limit(100)
    docs = await asyncio.to_thread(_get_docs_sync, query)
    return [doc.get('text', '') for doc in docs if 'text' in doc]