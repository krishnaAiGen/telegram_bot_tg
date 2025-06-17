# src/core_logic/initiate_topic.py
import random
import numpy as np
from datetime import datetime

from src.core_logic.llm_personas import PersonaManager
from src.services.fetch_db import get_last_100_message_texts
from src.services.openai_chat import get_llm_response

class ConversationPlanner:
    """Plans and schedules a new multi-bot conversation to initiate activity."""
    def __init__(self, persona_manager: PersonaManager):
        self.persona_manager = persona_manager

    async def _get_new_topic(self, db, config: dict) -> str:
        """Generates a new discussion topic based on recent channel history."""
        chat_messages = await get_last_100_message_texts(config['source_channel'], db)
        chat_context = " ".join([msg for msg in chat_messages if len(msg.split()) > 2])
        if not chat_context: return ""

        prompt = (
            f"Based on this chat history: \"{chat_context[:2000]}\". "
            f"Generate one single, new, engaging topic for discussion. "
            f"State only the topic itself in 5-10 words."
        )
        return await get_llm_response(prompt)

    def _distribute_personas_by_time(self, personas: list[dict]) -> dict:
        """
        Distributes a list of selected persona objects across different timeframes.
        Returns a dictionary mapping persona_name to a time delay tuple.
        """
        if not personas: return {}
        
        percentages = [0.5, 0.3, 0.2]
        timeframes = [(5, 720), (720, 1080), (1080, 1440)] # (5m-12h), (12h-18h), (18h-24h)
        
        num_items = [round(len(personas) * p) for p in percentages]
        # Adjust for rounding errors to ensure the sum matches the total number of personas
        while sum(num_items) > len(personas): num_items[0] -= 1
        while sum(num_items) < len(personas): num_items[0] += 1
        
        random.shuffle(personas)
        result, persona_counter = {}, 0
        for i, count in enumerate(num_items):
            for _ in range(count):
                if persona_counter < len(personas):
                    persona = personas[persona_counter]
                    result[persona['persona_name']] = timeframes[i]
                    persona_counter += 1
        return result

    async def plan_conversation(self, db, config: dict) -> tuple[dict, str]:
        """
        Creates a full conversation plan using the modern PersonaManager.
        Returns a dictionary ready to be saved by the StateManager.
        """
        topic = await self._get_new_topic(db, config)
        if not topic or "Error:" in topic: return {}, ""

        print(f"Planning new conversation around topic: {topic}")
        
        # 1. Select the number of bots for this conversation
        num_bots = random.randint(config.get('min_convo_bots', 2), config.get('max_convo_bots', 10))
        
        # 2. Randomly sample full persona objects from the PersonaManager
        available_personas = self.persona_manager.all_personas
        if num_bots > len(available_personas):
            num_bots = len(available_personas)
        selected_personas = random.sample(available_personas, num_bots)
        
        # 3. Distribute these personas across timeframes
        timeframe_dict = self._distribute_personas_by_time(selected_personas)

        conversation_dict = {} # Final plan: {persona_name: {delay_minutes, message, telegram_user}}
        
        for persona_obj in selected_personas:
            persona_name = persona_obj['persona_name']

            # 4. Generate a unique reply for each persona
            random_words = random.randint(20, 50)
            emoji_text = "with emojis" if random.choice([True, False]) else "without emojis"
            prompt = (
                f"{persona_obj['description']}. People are discussing '{topic}'. "
                f"What do you think? Write a response within {random_words} words {emoji_text}. "
                f"Do not reveal your persona identity."
            )
            persona_reply = await get_llm_response(prompt)
            
            # 5. Assign the random delay
            timeframe = timeframe_dict.get(persona_name, (5, 60))
            time_in_minutes = random.randint(timeframe[0], timeframe[1])

            # 6. Build the final dictionary entry for this persona's action
            conversation_dict[persona_name] = {
                "delay_minutes": time_in_minutes,
                "message": persona_reply,
                "telegram_user": persona_obj.get("telegram_user")
            }

        return conversation_dict, topic