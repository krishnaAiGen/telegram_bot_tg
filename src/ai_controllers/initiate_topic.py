# initiate_topic.py
import random
import json
import numpy as np
from datetime import datetime, timedelta
from openai_chat import get_llm_response
from llm_personas import PersonaManager
from fetch_db import get_last_100_message_texts

class ConversationPlanner:
    """Plans and schedules a new multi-bot conversation to initiate activity."""
    def __init__(self, config: dict, persona_manager: PersonaManager):
        self.config = config
        self.persona_manager = persona_manager
        with open('personas.json', 'r') as f:
            self.personas_index = json.load(f)

    async def _get_new_topic(self, db) -> str:
        """Generates a new discussion topic based on recent channel history."""
        chat_messages = await get_last_100_message_texts(self.config['source_channel'], db)
        chat_context = " ".join([msg for msg in chat_messages if len(msg.split()) > 2])
        prompt = (
            f"Based on this chat history: \"{chat_context[:2000]}\". "
            f"Generate a single, new, engaging topic for discussion. "
            f"State only the topic itself in 5-10 words."
        )
        return await get_llm_response(prompt)

    def _divide_list_by_timeframes(self, bot_indices: list) -> dict:
        """
        Preserves the original logic for distributing bots across timeframes.
        Assigns each bot index to a specific time window (min, max minutes).
        """
        if not bot_indices:
            return {}

        percentages = [0.5, 0.3, 0.2]
        timeframes = [(5, 720), (720, 1080), (1080, 1440)] # (5m-12h), (12h-18h), (18h-24h)

        total_items = len(bot_indices)
        num_items = [round(total_items * p) for p in percentages]

        # Adjust rounding errors to ensure the sum matches the total number of bots
        while sum(num_items) > total_items:
            num_items[0] -= 1
        while sum(num_items) < total_items:
            num_items[0] += 1

        # Shuffle the bot indices to randomize who gets which timeframe
        random.shuffle(bot_indices)

        result = {}
        index_counter = 0
        for i, count in enumerate(num_items):
            for _ in range(count):
                if index_counter < len(bot_indices):
                    bot_index = bot_indices[index_counter]
                    result[bot_index] = timeframes[i]
                    index_counter += 1
        return result

    async def plan_conversation(self, db) -> tuple[dict, str]:
        """
        Creates a full conversation plan with scheduled messages.
        Returns a tuple: (schedule_dictionary, topic_string)
        The schedule dict maps a future timestamp to [persona, message].
        """
        topic = await self._get_new_topic(db)
        if not topic or "Error:" in topic:
            return {}, ""

        print(f"Planning new conversation around topic: {topic}")

        # --- Bot Selection Logic (Preserved) ---
        number_of_bots_involved = random.randint(2, 10)
        bot_indices = list(set(np.random.randint(0, 10, size=number_of_bots_involved)))
        
        # --- Time Planning Logic (Preserved) ---
        timeframe_dict = self._divide_list_by_timeframes(bot_indices)

        # --- Message Generation ---
        conversation_dict = {} # Maps persona -> {time_in_minutes: message}
        first_persona = ""

        for index in bot_indices:
            persona = self.personas_index.get(str(index))
            if not persona:
                continue

            # This preserves your logic of having a slightly different prompt for the first bot
            if not first_persona:
                first_persona = persona
                prompt = (
                    f"{self.persona_manager.prompts[persona]}. People are discussing '{topic}'. "
                    f"What do you think? Write a response within 20 words with emojis. Don't reveal you are {persona}."
                )
            else:
                random_words = random.randint(20, 50)
                emoji_text = "with emojis" if random.choice([True, False]) else "without emojis"
                prompt = (
                    f"{self.persona_manager.prompts[persona]}. People are discussing '{topic}'. "
                    f"What do you think? Write a response within {random_words} words {emoji_text}. Don't reveal you are {persona}."
                )

            persona_reply = await get_llm_response(prompt)
            
            # Get the assigned time window and pick a random minute within it
            timeframe = timeframe_dict.get(index, (5, 60)) # Default to 5-60 mins if something fails
            time_in_minutes = random.randint(timeframe[0], timeframe[1])

            conversation_dict[persona] = {time_in_minutes: persona_reply}

        # --- Final Schedule Creation ---
        # This logic is what your old `store_initiate_conversation` function did.
        # It creates the final schedule to be saved to a file.
        schedule = {}
        now = datetime.now()
        
        # Sort by planned time to ensure chronological order
        sorted_convo = sorted(conversation_dict.items(), key=lambda x: list(x[1].keys())[0])

        for persona, time_msg_dict in sorted_convo:
            minutes_to_add = list(time_msg_dict.keys())[0]
            message = list(time_msg_dict.values())[0]
            
            future_time = now + timedelta(minutes=minutes_to_add)
            # Using a precise key to avoid overwriting messages scheduled in the same hour
            schedule_key = future_time.strftime("%Y-%m-%d %H:%M:%S")
            schedule[schedule_key] = [persona, message]

        return schedule, topic