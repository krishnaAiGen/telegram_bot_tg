# src/ai_controllers/initiate_topic.py
import random
import json
import numpy as np
from datetime import datetime
from llm_personas import PersonaManager
from fetch_db import get_last_100_message_texts
from openai_chat import get_llm_response

class ConversationPlanner:
    """Plans and schedules a new multi-bot conversation to initiate activity."""
    def __init__(self, persona_manager: PersonaManager):
        self.persona_manager = persona_manager
        # Loads the original personas.json for its numeric index mapping
        with open('personas.json', 'r') as f:
            self.personas_index_map = json.load(f)

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

    def _divide_list_by_timeframes(self, bot_indices: list) -> dict:
        """Preserves the original logic for distributing bots across timeframes."""
        if not bot_indices: return {}
        percentages = [0.5, 0.3, 0.2]
        timeframes = [(5, 720), (720, 1080), (1080, 1440)]
        total_items = len(bot_indices)
        num_items = [round(total_items * p) for p in percentages]

        while sum(num_items) > total_items: num_items[0] -= 1
        while sum(num_items) < total_items: num_items[0] += 1
        
        random.shuffle(bot_indices)
        result, index_counter = {}, 0
        for i, count in enumerate(num_items):
            for _ in range(count):
                if index_counter < len(bot_indices):
                    bot_index = bot_indices[index_counter]
                    result[bot_index] = timeframes[i]
                    index_counter += 1
        return result

    async def plan_conversation(self, db, config: dict) -> tuple[dict, str]:
        """Creates a full conversation plan, preserving the original complex logic."""
        topic = await self._get_new_topic(db, config)
        if not topic or "Error:" in topic: return {}, ""

        print(f"Planning new conversation around topic: {topic}")
        
        # Select bots using the original numeric index method
        num_bots = random.randint(config.get('min_convo_bots', 2), config.get('max_convo_bots', 10))
        max_index = len(self.personas_index_map) - 1
        bot_indices = list(set(np.random.randint(0, max_index + 1, size=num_bots)))
        timeframe_dict = self._divide_list_by_timeframes(bot_indices)

        conversation_dict = {} # Maps persona_name -> {time_in_minutes: message}
        
        for index in bot_indices:
            persona_name = self.personas_index_map.get(str(index))
            if not persona_name: continue

            # Find the full persona object to get its description
            persona_obj = next((p for p in self.persona_manager.all_personas if p['persona_name'] == persona_name), None)
            if not persona_obj: continue

            random_words = random.randint(20, 50)
            emoji_text = "with emojis" if random.choice([True, False]) else "without emojis"
            prompt = (
                f"{persona_obj['description']}. People are discussing '{topic}'. "
                f"What do you think? Write a response within {random_words} words {emoji_text}. "
                f"Do not reveal your persona identity."
            )
            persona_reply = await get_llm_response(prompt)
            
            timeframe = timeframe_dict.get(index, (5, 60))
            time_in_minutes = random.randint(timeframe[0], timeframe[1])

            conversation_dict[persona_name] = {time_in_minutes: persona_reply}

        return conversation_dict, topic