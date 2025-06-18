# src/core_logic/llm_personas.py
import random
import re
from config.settings import CHARACTERS_DATA

class PersonaManager:
    """
    Manages persona definitions from characters.json.
    Its primary roles are to load, structure, and provide easy access to persona data.
    """
    def __init__(self):
        # Load the utility prompts (e.g., for 'Human' replies) from the central config.
        self.utility_prompts = CHARACTERS_DATA.get("utility_personas", {})
        
        # --- Pre-processing Step: Flatten character data into a single persona list ---
        self.all_personas = []
        for character in CHARACTERS_DATA.get("characters", []):
            for persona in character.get("personas", []):
                # Create a copy and enrich it with parent character info.
                # This makes it easy to find which Telegram account is responsible for a persona.
                persona_copy = persona.copy()
                persona_copy['character_name'] = character.get('character_name')
                persona_copy['telegram_user'] = character.get('telegram_user')
                self.all_personas.append(persona_copy)
        
        if not self.all_personas:
            raise ValueError("No main personas found in characters.json. Bot cannot function.")
            
        print(f"Initialized PersonaManager with {len(self.all_personas)} main personas and {len(self.utility_prompts)} utility personas.")

    def get_persona_by_name(self, name: str) -> dict | None:
        """A simple utility to find and return a full persona object given its name."""
        return next((p for p in self.all_personas if p['persona_name'] == name), None)

    def get_random_persona(self) -> dict | None:
        """Selects a random persona object, primarily used for initiating conversations."""
        return random.choice(self.all_personas) if self.all_personas else None

    def format_personas_for_prompt(self) -> str:
        """
        Creates a structured, detailed string of all available personas and their profiles.
        This is the critical function for building the "Super Prompt" that lets the LLM choose the persona.
        """
        persona_profiles = []
        for p in self.all_personas:
            profile = f"""
### Persona: {p['persona_name']}
**Role:** {p.get('role', 'N/A')}
**Signature Voice:** Tone is {p.get('signature_voice', {}).get('tone', 'neutral')}, style is {p.get('signature_voice', {}).get('style', 'direct')}.
**Use Emojis:** {p.get('allow_emojis', False)}
**Example Reply:** "{p.get('examples', [{}])[0].get('assistant', 'N/A')}"
"""
            persona_profiles.append(profile)
        
        return "\n".join(persona_profiles)