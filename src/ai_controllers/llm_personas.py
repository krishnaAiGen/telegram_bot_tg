# llm_personas.py
import json
import random
from sentence_transformers import SentenceTransformer, util
from openai_chat import get_llm_response

class PersonaManager:
    """Manages persona selection (both relevant and random) and response generation."""
    def __init__(self, prompts_path='prompt.json', model_name='all-MiniLM-L6-v2'):
        # --- 1. Load Prompts and Persona Lists ---
        # This remains the same: loading configuration data.
        with open(prompts_path, 'r', encoding='utf-8') as json_file:
            self.prompts = json.load(json_file)
        
        self.non_chat_personas = {'Human', 'randomness', 'generate_topic'}
        self.chat_personas = [p for p in self.prompts.keys() if p not in self.non_chat_personas]

        # --- 2. Load the Similarity Model (CRITICAL) ---
        # The SentenceTransformer model is now loaded ONCE when the class is created.
        # This is highly efficient as it's not reloaded on every message.
        print("Loading SentenceTransformer model for persona similarity...")
        self.sim_model = SentenceTransformer(model_name)
        print("Model loaded.")

        # --- 3. Pre-compute Persona Embeddings (OPTIMIZATION) ---
        # To make a decision, we need to compare the message embedding to each persona's
        # description embedding. We can pre-calculate the persona embeddings once.
        self.persona_embeddings = {
            persona: self.sim_model.encode(self.prompts[persona], convert_to_tensor=True)
            for persona in self.chat_personas
        }
        print("Pre-computed embeddings for all personas.")


    def get_most_relevant_persona(self, message: str) -> str:
        """
        Determines the best persona by calculating cosine similarity.
        This RESTORES your original, more complex logic.
        """
        if not message:
            return self.get_random_persona() # Fallback for empty messages

        # 1. Compute embedding for the incoming message.
        message_embedding = self.sim_model.encode(message, convert_to_tensor=True)

        # 2. Calculate similarity against all pre-computed persona embeddings.
        similarities = {}
        for persona, persona_embedding in self.persona_embeddings.items():
            # util.pytorch_cos_sim computes the similarity score between the two embeddings.
            similarity = util.pytorch_cos_sim(message_embedding, persona_embedding).item()
            similarities[persona] = similarity

        # 3. Find the persona with the highest similarity score.
        if not similarities:
            return self.get_random_persona() # Fallback if something goes wrong

        most_relevant_persona = max(similarities, key=similarities.get)
        print(f"Most relevant persona for message is '{most_relevant_persona}' with score {similarities[most_relevant_persona]:.2f}")
        
        return most_relevant_persona

    def get_random_persona(self) -> str:
        """
        Selects a random persona. This is needed for initiating conversations
        when there is no message to analyze.
        """
        return random.choice(self.chat_personas)

    async def generate_reaction(self, persona: str, text: str) -> str:
        """Generates a contextual reply for a given persona reacting to text."""
        prompt = (
            f"{self.prompts[persona]} "
            f"You are in a group chat. Craft a thoughtful and relevant reply in 20-50 words to the following statement. "
            f"Use emojis to seem natural. Do not reveal you are a persona. Statement: \"{text}\""
        )
        return await get_llm_response(prompt)

    async def generate_human_like_reply(self, text: str) -> str:
        """Generates a generic, human-like reply based on the 'Human' persona prompt."""
        prompt = f"{self.prompts['Human']} for this message: \"{text}\""
        return await get_llm_response(prompt)