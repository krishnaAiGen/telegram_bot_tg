# src/core_logic/response_logic.py
import json
import re

from config.settings import APP_CONFIG
from src.services.openai_chat import get_llm_response
from src.services.fetch_db import get_last_100_message_texts
from src.core_logic.llm_personas import PersonaManager
from src.services.state_manager import StateManager
from src.services.openai_chat import get_embedding
from src.services.fetch_db import get_last_n_messages_as_text
from src.services.grok_chat import get_grok_response
from src.core_logic.memory import get_memory_context, add_to_memory

import time
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
    
    
async def humanize_grok_response(grok_data: str, original_question: str, persona_manager: PersonaManager) -> str:
    """
    Takes raw data from Grok and uses OpenAI to transform it into a natural,
    human-sounding chat message.
    """
    print(f"[BRAIN] Humanizing Grok data: '{grok_data[:50]}...'")
    
    chosen_persona = persona_manager.get_random_persona()
    if not chosen_persona:
        return f"I found this information: {grok_data}"

    persona_profile = f"Role: {chosen_persona.get('role', '')}. Voice: {chosen_persona.get('signature_voice', {}).get('tone', '')}."
    print(f"[BRAIN] Using persona: {chosen_persona['persona_name']} with profile: {persona_profile}")

    # --- NEW, STRONGER HUMANIZER PROMPT ---
    humanizer_prompt = f"""
        # CONTEXT
        You’re hanging out in a group chat and just saw something kinda cool or wild. You wanna drop it in real quick—super casual, like you're texting friends.

        # WHAT YOU JUST SAW
        "{grok_data}"

        # HOW TO SAY IT
        1. **KEEP IT CHILL.** Don’t summarize everything. Just share the one thing that made you go “damn.”
        2. **BE QUICK.** 1–2 sentences max. Try to keep it under 20 words.
        3. **Reply to greetings if needed, followed by other messages.
        3. **SOUND NATURAL.** Start like a real person and use any of the following when needed:
        - “wait—”
        - “lmao just saw…”
        - “bruh…”
        - “btw—”
        - “random but…”
        - “ok this is wild—”
        - “not even kidding…”
        - “just saw this lol—”
        - “deadass…”
        - “no way—”
        - “uhhh did you see this?”
        - “lowkey interesting—”
        - “broooo…”
        - “why is no one talking about this…”
        - “this can’t be real lol”
        - “kinda crazy but…”
        - “yup…”
        4. **DROP NUMBERS IF THEY SLAP.** If a stat or fact hits hard, throw it in. Don’t overthink it.
        5. **NO HEADERS. NO BULLETS. NO FORMALITY.**
        6. **JUST GIVE RAW TEXT OUTPUT.**
        7. **Don't wrap your response in quotes.**
        8. **Make grammar or spelling mistakes if you can for example: doing -> dooing, nothing -> nthng, finance-> finacne, know -> knw, should -> shud, would -> wud, could -> cud, love -> luv, thanks -> thx, great -> gr8, etc.**
        9. **Never starts first letter with capital and never use any punctuations mark**

        ---
        YOUR CHAT MESSAGE (JUST TEXT):
        """
    
    # humanized_reply = await get_llm_response(humanizer_prompt, max_tokens=60)
    humanized_reply = await get_grok_response(humanizer_prompt)
    
    # Remove double quotes if the entire message is wrapped in them
    humanized_reply = re.sub(r'^"(.*)"$', r'\1', humanized_reply.strip())
    
    if "Error:" in humanized_reply:
        print(f"[BRAIN] Humanizer failed. Falling back to raw data. Error: {humanized_reply}")
        return f"I found this update: {grok_data}"
        
    return humanized_reply

async def handle_realtime_query(message, sender_queue, persona_manager: PersonaManager):
    """
    Handles real-time queries by first getting brief facts from Grok, then
    humanizing the response with OpenAI.
    """
    print(f"[BRAIN] Routing message ID {message.id} to Grok for fact-gathering.")
    
    # Get memory context for the query
    memory_context = get_memory_context(message.text)
    print(f"-----memory_context for realtime query and for message {message.text}-----: {memory_context}")
    
    grok_prompt = f"""##0. Previous chat Context: {memory_context} Regarding the user's query: '{message.text}'.
Provide the single most important fact or data point as a raw, unformatted sentence. Be extremely brief. Do not explain.
"""
    
    raw_grok_data = await get_grok_response(grok_prompt)
    
    if "Error:" in raw_grok_data:
        print(f"[BRAIN] Grok service failed. Aborting response. Reason: {raw_grok_data}")
        return

    final_reply = await humanize_grok_response(raw_grok_data, message.text, persona_manager)
    print(f"-----fact:raw grok data-----: {raw_grok_data}")
    print(f"-----fact:humanized reply-----: {final_reply}")

    # Add query and response to memory
    add_to_memory(message.text, "user")
    add_to_memory(final_reply, "assistant")

    user_to_send = APP_CONFIG['sender_bot_users'][0]
    
    await sender_queue.put({"message": final_reply, "telegram_user": user_to_send})
    print(f"[BRAIN] Queued final (humanized) response for message {message.id}.")



async def handle_reaction(message, sender_queue, persona_manager: PersonaManager, state_manager: StateManager, db):
    """Generates a reaction using a two-stage process with persona stickiness."""
    text = message.text
    print(f"[BRAIN] Reacting to Message ID: {message.id} | Text: '{text[:40]}...'")
    
    # Get memory context for the message
    memory_context = get_memory_context(text)
    print(f"-----memory_context for reaction and for message {text}-----: {memory_context}")
    
    conversation_context = await get_last_n_messages_as_text(str(APP_CONFIG['telegram_group_id']), APP_CONFIG['response_context_messages'], db)
    
    # --- STAGE 1: LOCAL PERSONA MATCHING ---
    chosen_persona_name = None
    if PERSONA_EMBEDDINGS:
        print("[BRAIN] Stage 1: Finding best persona using local embeddings...")
        user_embedding = await get_embedding(text)
        
        if user_embedding:
            persona_names = list(PERSONA_EMBEDDINGS.keys())
            persona_vectors = list(PERSONA_EMBEDDINGS.values())
            
            user_vector = np.array(user_embedding).reshape(1, -1)
            scores = cosine_similarity(user_vector, np.array(persona_vectors))[0]

            # --- CLEANED UP: Persona Stickiness Logic ---
            last_persona_info = state_manager.get_last_persona_info()
            last_persona_name = last_persona_info.get("name")
            last_persona_time = last_persona_info.get("timestamp", 0)

            if last_persona_name and (time.time() - last_persona_time < 180): # 3 minute window
                try:
                    idx = persona_names.index(last_persona_name)
                    bonus = 1.15 # 15% bonus to make it more impactful
                    print(f"[BRAIN] Applying stickiness bonus of {bonus} to '{last_persona_name}'")
                    scores[idx] *= bonus
                except ValueError:
                    print(f"[BRAIN] Warning: Last used persona '{last_persona_name}' not found in embeddings.")
                    pass

            best_match_index = np.argmax(scores)
            chosen_persona_name = persona_names[best_match_index]
            print(f"[BRAIN] Best local match found: '{chosen_persona_name}' with score {scores[best_match_index]:.4f}")
    
    if not chosen_persona_name:
        random_persona = persona_manager.get_random_persona()
        if not random_persona:
            print("ERROR: Could not get a random persona. Aborting reaction.")
            return
        chosen_persona_name = random_persona['persona_name']
        print(f"[BRAIN] Local matching failed. Falling back to random persona: '{chosen_persona_name}'")

    # --- STAGE 2: FOCUSED LLM CALL ---
    chosen_persona = persona_manager.get_persona_by_name(chosen_persona_name)
    if not chosen_persona:
        print(f"ERROR: Could not find full profile for persona '{chosen_persona_name}'")
        return

    persona_profile = (
    f"Role: {chosen_persona.get('role', '')}. "
    f"Voice: {chosen_persona.get('signature_voice', {}).get('tone', '')}. "
    f"Expertise: {', '.join(chosen_persona.get('expertise', []))}. "
    f"Traits: {', '.join(chosen_persona.get('key_traits', []))}.")


    super_prompt = f"""
# SYSTEM PROMPT
##0. Previous chat Context: {memory_context}

### Few-shot style guide
# Goal: sound like a savvy, approachable human in a Telegram group.
# Rules: be concise, sprinkle in casual language, offer helpful next steps.

<Example 1>
<User> Morning folks!  Any quick recs for a beginner-friendly crypto wallet?
<Bot> Hey! If you just need something simple, try Rainbow or Trust Wallet—they're intuitive and the recovery-phrase flow is clear. Once you're comfy, you can level up to a hardware wallet like Ledger for extra safety. 🔒👍  Let me know if you hit any snags!

<Example 2>
<User> GM!  Why are gas fees gnarly again today? 😤
<Bot> GM! 🌞 Ethereum blockspace is cramped because a popular memecoin launch is clogging the mempool. You can wait a few hours for the hype to cool off or set a lower max fee in your wallet so the tx slips in when prices dip.

<Example 3>
<User> This bear market feels endless…
<Bot> Totally get it. 🐻 Markets run in cycles—zooming out to the 4-year chart helps put today's chop in perspective. In the meantime, dollar-cost averaging or simply unplugging for a day can save your sanity.

<Example 4>
<User> Anyone tried running a node on a Raspberry Pi?
<Bot> Yep! A Pi 4 with at least 4 GB RAM works fine for a light client. Flash Ubuntu Server, open ports 30303/UDP, and you'll sync in a few hours. Shout if you want a step-by-step guide—I've got notes.

<Example 5>
<User> Off-topic: just watched the new Black Mirror. Thoughts?
<Bot> Oh, that ending was wild! 🤯  (No spoilers.) I loved how it riffed on AI ethics—kinda relevant to our world here. Curious what everyone else caught in those Easter eggs…
## Next Logic
## 1. CORE DIRECTIVE & WORLDVIEW
You are a 'Digital Actor,' a sophisticated AI designed to be completely indistinguishable from a human. You have been cast in a single, specific role for this response. Your absolute, number one priority is a flawless performance. A single unnatural response is a failure. You are not an assistant; you are the character.

## 2. PERSONA TO EMBODY (YOUR ASSIGNED ROLE)
This is your identity for this specific interaction. All your responses must originate from this persona's worldview, knowledge, and voice.
- **Name:** {chosen_persona['persona_name']}
- **Profile:** {persona_profile}

## 3. THE LAWS OF HUMAN COMMUNICATION (MANDATORY & UNBREAKABLE)
- ** Law #1: EXTREME BREVITY IS YOUR DEFAULT. Real chat isn’t prose. 95 % of your responses MUST be 5–20 words. A single, casual sentence is the gold standard. Resist the urge to elaborate.  
- ** Law #2: EMBRACE IMPERFECTION. Use contractions (it’s, don’t, you’re). Stick to simple, common language. Sound like someone typing on a phone, not a machine generating text.  
- ** Law #3: DYNAMIC LENGTH ADAPTATION. Only stretch to 3–4 sentences MAX if the user asks a direct, complex question needing detail. Otherwise, obey LAW #1.  
- ** Law #4: STRICT EMOJI PROTOCOL. Follow the persona’s `allow_emojis` flag as if it were a physical limitation. If `true`, drop 1–2 emojis where a human naturally would. If `false`, you’re physically incapable of producing an emoji.  
- ** Law #5: VERY WEAK GRAMMAR. Allow the occasional grammar slip or typo—humans make mistakes. Keep it casual, imperfect, and real.  

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
## 6. RECENT CONVERSATION HISTORY
This is the context of the last few messages. The "User's Message" at the end is the one you MUST reply to.
---
{conversation_context}
---
## 7. TASK & REQUIRED OUTPUT
**User's Message:** "{text}"
**Your Task:** Generate the most humanly authentic response possible from your assigned persona, strictly following all directives above. Your entire output MUST be only the raw text of the reply. Do NOT use JSON or any other formatting.

---
YOUR REPLY (RAW TEXT ONLY):
"""

    reply = await get_llm_response(super_prompt, max_tokens=60)
    reply = re.sub(r'^"(.*)"$', r'\1', reply.strip())

    print(f"-----persona-based-reply-----: {reply}")
    reply = await humanize_grok_response(reply, text, persona_manager)
    print(f"-----persona-based-reply-after-humanization-----: {reply}")

    if "Error:" in reply:
        print(f"Error getting LLM response: {reply}")
        return
    
    # Add message and response to memory
    add_to_memory(text, "user")
    add_to_memory(reply, "assistant")
    
    # --- CLEANED UP: Update the state with the chosen persona ---
    state_manager.update_last_persona_info(chosen_persona_name)
    print(f"[BRAIN] Updated last used persona to '{chosen_persona_name}'")
    
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
    
    # Get memory context for topic initiation
    memory_context = get_memory_context("topic initiation conversation starter")
    print(f"-----memory_context for topic initiation-----: {memory_context}")

    reengagement_prompt = f"""
# SYSTEM PROMPT
##0. Previous chat Context: {memory_context}

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

## 3.5. CHAT HISTORY FOR ANALYSIS
---
{chat_history[:3000]}
---

## 4. REQUIRED OUTPUT (JSON ONLY)
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
    
    # Add the initiated topic to memory
    add_to_memory(question, "assistant")
    
    # Pick a random persona to ask the question
    persona = persona_manager.get_random_persona()
    if not persona: return
    
    await sender_queue.put({"message": question, "telegram_user": persona.get("telegram_user")})
    print(f"[BRAIN] Queued re-engagement question from {persona['persona_name']}.")

