#!/usr/bin/env python3
"""
Simple Telegram Bot - Core Bot Logic

This version uses existing modules with configurable timing via .env variables.
Main entry point is in main.py.
"""

import asyncio
import random
import time
import os
import json
from collections import deque
from telethon import TelegramClient, events
from telethon.tl.types import PeerUser

# Import existing modules
from config.settings import APP_CONFIG, TELEGRAM_USERS
from src.core_logic.llm_personas import PersonaManager
from src.services.openai_chat import get_llm_response, is_content_offensive
from src.bot_config import print_bot_configuration, get_conversation_topics

class SimpleTelegramBot:
    def __init__(self):
        # Initialize memory with configurable sizes
        self.recently_processed = deque(maxlen=APP_CONFIG['max_recent_messages'])
        self.recently_sent = deque(maxlen=APP_CONFIG['max_sent_messages_cache'])
        self.last_activity = time.time()
        
        # Initialize existing components
        self.persona_manager = PersonaManager()
        self.clients = {}
        self.main_client = None
        
        # Print configuration for debugging
        print_bot_configuration(len(self.persona_manager.all_personas))
    
    async def start(self):
        """Start the bot"""
        # Setup clients
        await self._setup_clients()
        
        print(f"✅ Bot listening to @{APP_CONFIG['telegram_channel']}")
        print("📱 Press Ctrl+C to stop")
        
        # Start background tasks
        await asyncio.gather(
            self._run_main_client(),
            self._periodic_initiation(),
            return_exceptions=True
        )
    
    async def _setup_clients(self):
        """Setup Telegram clients using existing config"""
        for username, creds in TELEGRAM_USERS.items():
            client = TelegramClient(
                os.path.join(APP_CONFIG['data_dir'], username),
                int(creds['api_id']),
                creds['api_hash']
            )
            await client.start()
            self.clients[username] = client
            
            # Use ingestor as main client
            if username == APP_CONFIG['ingestor_bot_user']:
                self.main_client = client
                client.add_event_handler(
                    self._handle_message,
                    events.NewMessage(chats=[f"@{APP_CONFIG['telegram_channel']}"])
                )
    
    async def _run_main_client(self):
        """Keep main client running"""
        if self.main_client:
            await self.main_client.run_until_disconnected()
    
    async def _handle_message(self, event):
        """Handle incoming messages - configurable behavior"""
        message = event.message
        
        # Skip our own messages and known bots
        if self._should_skip_message(message):
            return
        
        print(f"📨 New message {message.id}: {message.text[:100]}...")
        
        # Configurable response logic
        if random.random() < APP_CONFIG['response_probability']:
            await self._process_response(message)
        else:
            print(f"🤐 Not responding to message {message.id} (probability: {APP_CONFIG['response_probability']*100:.0f}%)")
        
        # Mark as processed and update activity
        self.recently_processed.append(message.id)
        self.last_activity = time.time()
    
    def _should_skip_message(self, message):
        """Check if message should be skipped"""
        # Skip our own messages
        if message.text in self.recently_sent:
            print(f"⏭️  Skipping our own message")
            return True
        
        # Skip known bots
        sender_id = self._get_sender_id(message)
        if sender_id in APP_CONFIG.get('known_bot_ids', []):
            print(f"🤖 Skipping bot message from {sender_id}")
            return True
        
        # Skip if recently processed
        if message.id in self.recently_processed:
            print(f"⏭️  Already processed message {message.id}")
            return True
        
        return False
    
    async def _process_response(self, message):
        """Process response to a message"""
        print(f"🎯 Deciding to respond to message {message.id} (probability: {APP_CONFIG['response_probability']*100:.0f}%)")
        
        # Configurable delay
        delay = random.uniform(
            APP_CONFIG['min_response_delay_secs'], 
            APP_CONFIG['max_response_delay_secs']
        )
        print(f"⏰ Waiting {delay:.0f} seconds before responding...")
        await asyncio.sleep(delay)
        
        # Generate and send response
        await self._generate_response(message)
    
    async def _generate_response(self, message):
        """Generate response using existing response_logic with configurable OpenAI settings"""
        try:
            text = message.text
            print(f"🎭 Generating response to: '{text[:40]}...'")
            
            # Create prompt using existing persona logic
            super_prompt = self._create_response_prompt(text)
            
            # Get response using configurable OpenAI settings
            response_str = await get_llm_response(
                super_prompt, 
                model=APP_CONFIG['openai_model'],
                max_tokens=APP_CONFIG['openai_max_tokens']
            )
            
            # Parse and validate response
            name, reply = self._parse_llm_response(response_str)
            if not name or not reply:
                return
            
            # Safety check using existing moderation
            if await is_content_offensive(reply):
                print("🛡️  Blocked unsafe response")
                return
            
            # Send message
            persona_obj = self.persona_manager.get_persona_by_name(name)
            telegram_user = persona_obj.get("telegram_user") if persona_obj else APP_CONFIG['sender_bot_users'][0]
            
            await self._send_message(reply, telegram_user)
            print(f"✅ Sent response from {name}")
            
        except Exception as e:
            print(f"❌ Error generating response: {e}")
    
    def _create_response_prompt(self, text):
        """Create response prompt using existing persona logic"""
        persona_profiles = [
            f"### Persona: {p['persona_name']}\n**Role:** {p.get('role', 'N/A')}" 
            for p in self.persona_manager.all_personas
        ]
        available_personas_text = "\n".join(persona_profiles)
        
        return f"""You are a master AI that simulates different expert personas in a chat group.
1. **Analyze**: Read the user's message: "{text}".
2. **Review Personas**: {available_personas_text}
3. **Select**: Choose the SINGLE best persona to respond.
4. **Generate**: Create a reply that perfectly matches the persona's voice (1-2 casual sentences).
5. **Format**: Provide a JSON object with two keys: "chosen_persona_name" and "reply".
---
YOUR JSON RESPONSE:"""
    
    def _parse_llm_response(self, response_str):
        """Parse LLM response and extract persona name and reply"""
        try:
            data = json.loads(response_str)
            name = data.get("chosen_persona_name")
            reply = data.get("reply")
            if not (name and reply):
                raise ValueError("Missing keys")
            return name, reply
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ Error parsing LLM response: {e}")
            return None, None
    
    async def _send_message(self, text, telegram_user=None):
        """Send message with configurable delays"""
        try:
            # Choose client
            if telegram_user and telegram_user in self.clients:
                client = self.clients[telegram_user]
            else:
                client = self.clients[APP_CONFIG['sender_bot_users'][0]]
            
            # Track sent message to avoid self-response
            self.recently_sent.append(text)
            
            # Send message
            await client.send_message(f"@{APP_CONFIG['telegram_channel']}", text)
            print(f"📤 Sent: {text[:100]}...")
            
            # Configurable delay between messages
            delay = random.uniform(
                APP_CONFIG['min_send_delay_secs'], 
                APP_CONFIG['max_send_delay_secs']
            )
            print(f"⏳ Waiting {delay:.0f} seconds before next action...")
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    async def _periodic_initiation(self):
        """Periodically initiate conversations with configurable timing"""
        check_interval = APP_CONFIG['initiation_check_interval_mins'] * 60
        
        while True:
            await asyncio.sleep(check_interval)
            
            hours_since_activity = (time.time() - self.last_activity) / 3600
            
            # Use random value between min and max initiate hours
            min_hours = APP_CONFIG['min_initiate_hours']
            max_hours = APP_CONFIG.get('max_initiate_hours', min_hours)
            threshold_hours = random.uniform(min_hours, max_hours) if max_hours > min_hours else min_hours
            
            if hours_since_activity >= threshold_hours:
                print(f"💡 Channel quiet for {hours_since_activity:.1f} hours (threshold: {threshold_hours:.1f}h), initiating...")
                await self._initiate_conversation()
                self.last_activity = time.time()
            else:
                print(f"🔍 Channel activity check: {hours_since_activity:.1f}h ago (threshold: {threshold_hours:.1f}h)")
    
    async def _initiate_conversation(self):
        """Initiate conversation with configurable OpenAI settings"""
        try:
            topics = get_conversation_topics()
            topic = random.choice(topics)
            persona = self.persona_manager.get_random_persona()
            
            if not persona:
                print("❌ No persona available for initiation")
                return
            
            # Generate contextual message with configurable settings
            prompt = f"Your persona is: {persona.get('role', 'Community member')}. Start a conversation about: '{topic}'. Write a short, casual, open-ended question (1-2 sentences)."
            message = await get_llm_response(
                prompt,
                model=APP_CONFIG['openai_model'],
                max_tokens=APP_CONFIG['openai_max_tokens']
            )
            
            if "Error:" not in message and message.strip():
                await self._send_message(message, persona.get("telegram_user"))
                print(f"✅ Initiated conversation from {persona['persona_name']}")
            else:
                print(f"❌ Failed to generate initiation message: {message}")
                
        except Exception as e:
            print(f"❌ Error initiating conversation: {e}")
    
    def _get_sender_id(self, message):
        """Extract sender ID from message"""
        sender_id_attr = getattr(message.sender, 'id', None)
        from_id_peer = getattr(message, 'from_id', None)
        from_id_attr = getattr(from_id_peer, 'user_id', None) if isinstance(from_id_peer, PeerUser) else None
        return sender_id_attr or from_id_attr
    
    async def stop(self):
        """Clean shutdown"""
        print("\n🛑 Shutting down...")
        for client in self.clients.values():
            await client.disconnect()
        print("✅ Bot stopped") 