# src/core_logic/llm_personas.py
import random
import re
from config.settings import CHARACTERS_DATA

class PersonaManager:
    """
    Manages persona definitions from characters.json.
    Its primary roles are to provide access to persona data and to format
    the persona list for injection into LLM prompts.
    """
    def __init__(self):
        # Load the utility prompts (e.g., for 'Human' replies) from the central config.
        self.utility_prompts = CHARACTERS_DATA.get("utility_personas", {})
        
        # --- Pre-processing Step: Flatten character data into a single persona list ---
        self.all_personas = []
        for character in CHARACTERS_DATA.get("characters", []):
            for persona in character.get("personas", []):
                # Create a copy and enrich it with parent character info.
                persona_copy = persona.copy()
                persona_copy['character_name'] = character.get('character_name')
                persona_copy['telegram_user'] = character.get('telegram_user')
                self.all_personas.append(persona_copy)
        
        if not self.all_personas:
            raise ValueError("No personas found in characters.json. Bot cannot function.")
            
        print(f"Initialized PersonaManager with {len(self.all_personas)} personas.")

    def get_persona_by_name(self, name: str) -> dict | None:
        """A simple utility to find and return a full persona object given its name."""
        return next((p for p in self.all_personas if p['persona_name'] == name), None)

    def get_random_persona(self) -> dict | None:
        """Selects a random persona object, primarily used for initiating conversations."""
        return random.choice(self.all_personas) if self.all_personas else None

    def format_personas_for_prompt(self) -> str:
        """
        Creates a formatted string of all available personas and their descriptions.
        This is the critical function for building the "Super Prompt" that lets the LLM choose the persona.
        """
        formatted_list = []
        for persona in self.all_personas:
            formatted_list.append(
                f"- Persona Name: \"{persona['persona_name']}\"\n"
                f"  Description: \"{persona['description']}\""
            )
        return "\n\n".join(formatted_list)
        
    def refine_reply(self, message: str) -> str:
        """A preserved utility function from your original code to clean up LLM output text."""
        response_text = message.replace('\n', ' ')
        # This regex is preserved but improved to keep basic punctuation for a more natural feel.
        cleaned_text = re.sub(r'[^a-zA-Z0-9 .,!?\'":-]', '', response_text)
        return re.sub(r'\s+', ' ', cleaned_text).strip()