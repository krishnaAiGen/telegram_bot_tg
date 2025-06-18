import json
import firebase_admin
from firebase_admin import credentials, firestore

from config.settings import APP_CONFIG, CHARACTERS_DATA
from src.services.openai_chat import get_llm_response, is_content_offensive
from src.services.fetch_db import get_last_100_message_texts
from src.core_logic.llm_personas import PersonaManager

async def handle_reaction(message, sender_queue, persona_manager: PersonaManager):
    """Generates a reaction to a message and puts it in the sender_queue."""
    text = message.text
    print(f"Brain: Reacting to Message ID: {message.id} | Text: '{text[:40]}...'")

    persona_profiles = [
        f"### Persona: {p['persona_name']}\n**Role:** {p.get('role', 'N/A')}" for p in persona_manager.all_personas
    ]
    available_personas_text = "\n".join(persona_profiles)

    super_prompt = f"""You are a master AI that simulates different expert personas in a chat group.
1. **Analyze**: Read the user's message: "{text}".
2. **Review Personas**: {available_personas_text}
3. **Select**: Choose the SINGLE best persona to respond.
4. **Generate**: Create a reply that perfectly matches the persona's voice (1-2 casual sentences).
5. **Format**: Provide a JSON object with two keys: "chosen_persona_name" and "reply".
---
YOUR JSON RESPONSE:"""

    response_str = await get_llm_response(super_prompt)
    try:
        data = json.loads(response_str)
        name, reply = data.get("chosen_persona_name"), data.get("reply")
        if not (name and reply): raise ValueError("Missing keys")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing LLM response: {e}. Response: '{response_str}'")
        return

    if await is_content_offensive(reply):
        print("Offensive reply blocked.")
        return

    persona_obj = persona_manager.get_persona_by_name(name)
    user = persona_obj.get("telegram_user") if persona_obj else APP_CONFIG['sender_bot_users'][0]
    
    await sender_queue.put({"message": reply, "telegram_user": user})
    print(f"Brain: Queued reply from {name} for message {message.id}.")

async def handle_initiation(sender_queue, persona_manager: PersonaManager):
    """Generates a new topic and queues it for sending."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(APP_CONFIG['firebase_cred_path'])
        firebase_admin.initialize_app(cred, name='bot_brain_init_app')
    db = firestore.client(app=firebase_admin.get_app(name='bot_brain_init_app'))

    messages = await get_last_100_message_texts(APP_CONFIG['telegram_channel'], db)
    if not messages:
        print("Brain: No chat history found to initiate topic.")
        return

    chat_history = "\n".join(messages)
    topic_prompt = f'{CHARACTERS_DATA["utility_personas"]["generate_topic"]}\n\nChat History:\n"""\n{chat_history[:2000]}\n"""'
    new_topic = await get_llm_response(topic_prompt)

    if "Error:" in new_topic or not new_topic.strip():
        print(f"Brain: Could not generate a new topic. LLM said: {new_topic}")
        return
    print(f"Brain: Generated new topic: {new_topic}")
    
    persona = persona_manager.get_random_persona()
    if not persona: return
    
    prompt = f"Your persona is: {persona.get('role')}. Start a conversation about: '{new_topic}'. Write a short, casual, open-ended question (1-2 sentences)."
    message = await get_llm_response(prompt)
    
    await sender_queue.put({"message": message, "telegram_user": persona.get("telegram_user")})
    print(f"Brain: Queued initiation message from {persona['persona_name']}.")