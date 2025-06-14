# src/ai_controllers/llm_personas.py
import random
import re
from sentence_transformers import SentenceTransformer, util
from openai_chat import get_llm_response
from config import CHARACTERS_DATA

class PersonaManager:
    """Manages persona selection and response generation based on characters.json."""
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.utility_prompts = CHARACTERS_DATA.get("utility_personas", {})
        self.all_personas = []
        for character in CHARACTERS_DATA.get("characters", []):
            for persona in character.get("personas", []):
                persona_copy = persona.copy()
                persona_copy['character_name'] = character.get('character_name')
                persona_copy['telegram_user'] = character.get('telegram_user')
                self.all_personas.append(persona_copy)
        
        if not self.all_personas:
            raise ValueError("No personas found in characters.json. Bot cannot function.")

        print("Loading SentenceTransformer model for persona similarity...")
        self.sim_model = SentenceTransformer(model_name)
        
        self.persona_embeddings = {
            p['persona_name']: self.sim_model.encode(p['description'], convert_to_tensor=True)
            for p in self.all_personas
        }
        print(f"Initialized PersonaManager with {len(self.all_personas)} personas.")

    def get_most_relevant_persona(self, message: str) -> dict | None:
        """Determines the best persona by calculating cosine similarity."""
        if not message: return self.get_random_persona()
        
        message_embedding = self.sim_model.encode(message, convert_to_tensor=True)
        similarities = {
            name: util.pytorch_cos_sim(message_embedding, emb).item()
            for name, emb in self.persona_embeddings.items()
        }
        
        if not similarities: return self.get_random_persona()
        
        best_persona_name = max(similarities, key=similarities.get)
        highest_score = similarities[best_persona_name]
        
        if highest_score < 0.2: # Relevance threshold
            print(f"No relevant persona found (top score {highest_score:.2f}). Falling back to random.")
            return self.get_random_persona()
            
        return next((p for p in self.all_personas if p['persona_name'] == best_persona_name), None)

    def get_random_persona(self) -> dict | None:
        """Selects a random persona object."""
        return random.choice(self.all_personas) if self.all_personas else None

    async def generate_reaction(self, persona: dict, context: str) -> str:
        """Generates a contextual reply for a given persona object."""
        prompt = (
            f"You are the persona: {persona['description']}\n"
            f"Here is the recent conversation history:\n---\n{context}\n---\n"
            f"Based on this history, provide a relevant and concise reply as your persona."
        )
        return await get_llm_response(prompt)

    async def generate_human_like_reply(self, text: str) -> str:
        """Generates a generic, human-like reply."""
        human_prompt = self.utility_prompts.get('Human', 'Reply like a human to this:')
        return await get_llm_response(f"{human_prompt} \"{text}\"")
        
    def refine_reply(self, message: str) -> str:
        """A preserved utility function to clean up text."""
        response_text = message.replace('\n', ' ')
        cleaned_text = re.sub(r'[^a-zA-Z0-9 .,!?\'":-]', '', response_text) # Keeping basic punctuation
        return re.sub(r'\s+', ' ', cleaned_text).strip()