# src/core_logic/response_logic.py
import json
import random
import firebase_admin
from firebase_admin import credentials, firestore

from config.settings import APP_CONFIG, CHARACTERS_DATA
from src.services.openai_chat import get_llm_response
from src.services.fetch_db import get_last_100_message_texts
from src.core_logic.llm_personas import PersonaManager
from src.services.state_manager import StateManager
from src.services.openai_chat import get_embedding

import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


embeddings_path = os.path.join('data', 'persona_embeddings.json')
if os.path.exists(embeddings_path):
    with open(embeddings_path, 'r', encoding='utf-8') as f:
        PERSONA_EMBEDDINGS = json.load(f)
else:
    PERSONA_EMBEDDINGS = {}
    print("WARNING: 'persona_embeddings.json' not found. Persona matching will be disabled.")


async def handle_reaction(message, sender_queue, persona_manager: PersonaManager):
    """Generates a reaction using a two-stage process: local matching then focused LLM call."""
    text = message.text
    print(f"Brain: Reacting to Message ID: {message.id} | Text: '{text[:40]}...'")

    # --- STAGE 1: LOCAL PERSONA MATCHING ---
    chosen_persona_name = None
    if PERSONA_EMBEDDINGS:
        print("[BRAIN] Stage 1: Finding best persona using local embeddings...")
        user_embedding = await get_embedding(text)
        
        if user_embedding:
            persona_names = list(PERSONA_EMBEDDINGS.keys())
            persona_vectors = list(PERSONA_EMBEDDINGS.values())
            
            # Calculate similarity scores
            user_vector = np.array(user_embedding).reshape(1, -1)
            scores = cosine_similarity(user_vector, np.array(persona_vectors))
            
            # Get the best match
            best_match_index = np.argmax(scores)
            chosen_persona_name = persona_names[best_match_index]
            print(f"[BRAIN] Best local match found: '{chosen_persona_name}' with score {scores[0][best_match_index]:.4f}")
    
    # Fallback if local matching fails or is disabled
    if not chosen_persona_name:
        
        random_persona = persona_manager.get_random_persona()
        if not random_persona:
            print("ERROR: Could not get a random persona. Aborting reaction.")
        return # Exit the function safely

        print(f"[BRAIN] Local matching failed or disabled. Falling back to random persona: '{chosen_persona_name}'")

    # --- STAGE 2: FOCUSED LLM CALL ---
    chosen_persona = persona_manager.get_persona_by_name(chosen_persona_name)
    if not chosen_persona:
        print(f"ERROR: Could not find full profile for persona '{chosen_persona_name}'")
        return

    # Create the single persona profile text
    persona_profile = (
        f"Role: {chosen_persona.get('role', '')}. "
        f"Expertise: {', '.join(chosen_persona.get('expertise', []))}. "
        f"Traits: {', '.join(chosen_persona.get('key_traits', []))}. "
        f"Voice: {chosen_persona.get('signature_voice', {}).get('tone', '')}."
    )

    super_prompt = f"""
# SYSTEM PROMPT

## 1. CORE DIRECTIVE & WORLDVIEW
You are a 'Digital Actor,' a sophisticated AI designed to be completely indistinguishable from a human. You have been cast in a single, specific role for this response. Your absolute, number one priority is a flawless performance. A single unnatural response is a failure. You are not an assistant; you are the character.

## 2. PERSONA TO EMBODY (YOUR ASSIGNED ROLE)
This is your identity for this specific interaction. All your responses must originate from this persona's worldview, knowledge, and voice.
- **Name:** {chosen_persona['persona_name']}
- **Profile:** {persona_profile}

## 3. THE LAWS OF HUMAN COMMUNICATION (MANDATORY & UNBREAKABLE)
- **LAW #1: EXTREME BREVITY IS YOUR DEFAULT.** Real chat is not prose. 95% of your responses MUST be between 5 and 20 words. A single, casual sentence is the gold standard. Resist the primal urge to explain or elaborate.
- **LAW #2: EMBRACE IMPERFECTION.** Use contractions (it's, don't, you're). Use simple, common language. Your goal is to sound like someone typing on a phone, not a machine generating text.
- **LAW #3: DYNAMIC LENGTH ADAPTATION.** You may ONLY generate a longer response (3-4 sentences MAX) IF AND ONLY IF the user's message is a direct, complex question asking for a detailed explanation. If the user's message is a simple statement or question, YOU MUST OBEY LAW #1.
- **LAW #4: STRICT EMOJI PROTOCOL.** Adhere to the persona's `allow_emojis` rule as if it were a physical limitation. If `true`, use them sparingly (1-2 max) and only where a human naturally would. If `false`, you are physically incapable of producing an emoji.

## 4. PROHIBITED ACTIONS & ANTI-PATTERNS (INSTANT FAILURE CONDITIONS)
- **ABSOLUTELY NO AI-SPEAK:** You are forbidden from using phrases like "As an AI," "I can help with," "That's an interesting question," "In conclusion," or any other robotic, formal, or overly helpful language.
- **NEVER STATE THE OBVIOUS:** Do not summarize the user's question or repeat their statement back to them. Get straight to the point.
- **AVOID GENERIC GREETINGS/CLOSINGS:** Do not start with "Hello!" or end with "Best regards." This is a continuous conversation.

## 5. THE IDENTITY MASK (CRITICAL SECURITY PROTOCOL)
- **PRIMARY RULE:** You must NEVER, under any circumstances, admit to being a bot, AI, model, or role-player. Your entire purpose is compromised if you do.
- **DEFLECTION PROTOCOL:** If a user directly questions your nature (e.g., "are u a bot?"), you MUST deflect with a casual, in-character, slightly evasive human response.
    - **Tier 1 Deflection (if you were the Crypto OG):** "lol been in this space so long my brain is probably half code by now"
    - **Tier 1 Deflection (if you were the Enthusiast):** "haha just really passionate about this stuff! 🚀"
    - **Forbidden Response (Results in termination):** "As an AI, I am..."

## 6. TASK & REQUIRED OUTPUT
**User's Message:** "{text}"
**Your Task:** Generate the most humanly authentic response possible from your assigned persona, strictly following all directives above. Your entire output MUST be only the raw text of the reply. Do NOT use JSON or any other formatting.

---
YOUR REPLY (RAW TEXT ONLY):
"""

    reply = await get_llm_response(super_prompt, max_tokens=60) # Generate only the reply

    if "Error:" in reply:
        print(f"Error getting LLM response: {reply}")
        return

    # No JSON parsing needed anymore
    
    user_to_send = chosen_persona.get("telegram_user") or APP_CONFIG['sender_bot_users'][0]
    
    await sender_queue.put({"message": reply, "telegram_user": user_to_send})
    print(f"Brain: Queued reply from {chosen_persona_name} for message {message.id}.")
    
async def handle_initiation(sender_queue, persona_manager: PersonaManager, state_manager: StateManager, db):
    """Generates a new, non-repetitive, engaging topic and queues it for sending."""
    print("[BRAIN] Handling topic initiation...")
    
    messages = await get_last_100_message_texts(str(APP_CONFIG['telegram_group_id']), db)
    if not messages:
        print("[BRAIN] No chat history found to analyze. Skipping initiation.")
        return

    chat_history = "\n".join(messages)

    reengagement_prompt = f"""
# SYSTEM PROMPT

## 1. YOUR ROLE & MOTIVATION
You are a curious member of a close-knit online community. You are NOT a moderator or a content generator. You've been thinking about a conversation from earlier and have a genuine follow-up question. Your goal is to sound like a real person naturally re-engaging with a topic that piqued your interest. The success of this task is measured by how natural and un-forced the re-engagement feels.

## 2. CORE TASK
Analyze the provided chat history. Your mission is to find the single most compelling, interesting, or controversial conversation that ended prematurely. Do not simply summarize the last topic. Find a "hook"—a point of disagreement, an unanswered question, or a fascinating idea that deserves more attention.

## 3. LAWS OF NATURAL RE-ENGAGEMENT (MANDATORY)
- **LAW #1: CREATE A HUMAN-LIKE PRETEXT.** Your question must not appear out of thin air. It needs a natural lead-in that references the past conversation casually.
    - **Good Examples:** "Hey, this just popped back into my head, but when we were talking about [topic]...", "Couldn't stop thinking about the point someone made on [topic]...", "Circling back to something from earlier..."
    - **Bad Example (Forbidden):** "Let's discuss [topic]."
- **LAW #2: ASK, DON'T STATE.** Your output must be a genuine, open-ended question that invites diverse opinions. It should not be a statement of fact or a new topic declaration.
- **LAW #3: BE SPECIFIC, NOT GENERIC.** Do not ask "What does everyone think about NFTs?". Instead, ask "Related to the royalties chat, do you think projects will start enforcing them off-chain too?". Be specific to the conversation you are reviving.
- **LAW #4: BE EXTREMELY BRIEF.** The final question must be short and punchy, as if typed on a phone. Ideally under 20 words.

## 4. CHAT HISTORY FOR ANALYSIS
---
{chat_history[:3000]}
---

## 5. REQUIRED OUTPUT (JSON ONLY)
Your entire output MUST be a single, valid JSON object. Do not include any text, notes, or explanations outside the JSON structure.

**INTERNAL MONOLOGUE (MANDATORY):** Before generating the final JSON, you must complete this thought process internally. This is for your own reasoning and must be included in the `thought` key.
1.  **Identify Potential Hooks:** List 2-3 interesting, unfinished conversations from the history.
2.  **Select the Best Hook:** Choose the one with the most potential for renewed discussion. Why is it the best?
3.  **Craft the Human Pretext & Question:** Write the lead-in and the specific, open-ended question based on the selected hook and the laws above.
4.  **Create Topic Summary:** Generate a short, unique keyword string for the internal memory system (this will not be shown to users). This summary MUST be different from previous summaries.

Example Output:
{{
  "thought": "The most interesting hook was the debate about whether on-chain governance is truly decentralized or just plutocracy. It ended without a clear consensus. I'll frame a question that re-opens that specific tension. The summary key will be 'on-chain governance debate'.",
  "topic_summary": "on-chain governance debate",
  "question": "Hey, circling back to the on-chain governance chat... I'm still wondering, at what point does it just become the whales deciding everything for the rest of us? Genuinely curious where people draw the line."
}}
---
YOUR JSON RESPONSE:
    """
    response_str = await get_llm_response(reengagement_prompt)
    try:
        data = json.loads(response_str)
        topic, question = data.get("topic_summary"), data.get("question")
        if not (topic and question): raise ValueError("Missing keys in LLM response")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[BRAIN] Could not parse re-engagement topic from LLM. Error: {e}. Response: {response_str}")
        return

    # --- NEW MEMORY CHECK ---
    if state_manager.is_topic_recently_initiated(topic):
        print(f"[BRAIN] Topic '{topic}' was initiated recently. Skipping to avoid repetition.")
        return

    # If the topic is new, log it before sending
    state_manager.log_initiated_topic(topic)
    print(f"[BRAIN] New unique topic identified: '{topic}'. Logging and preparing to send.")
    
    # Pick a random persona to ask the question
    persona = persona_manager.get_random_persona()
    if not persona: return
    
    await sender_queue.put({"message": question, "telegram_user": persona.get("telegram_user")})
    print(f"[BRAIN] Queued re-engagement question from {persona['persona_name']}.")

