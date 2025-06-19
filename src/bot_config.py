"""
Bot Configuration Display and Validation

This module handles configuration display and validation for the simple bot.
"""

from config.settings import APP_CONFIG

def print_bot_configuration(persona_count):
    """Print bot configuration for debugging"""
    print(f"✅ Bot initialized with {persona_count} personas")
    print(f"📊 Configuration:")
    print(f"   • Response probability: {APP_CONFIG['response_probability']*100:.0f}%")
    print(f"   • Response delay: {APP_CONFIG['min_response_delay_secs']:.0f}-{APP_CONFIG['max_response_delay_secs']:.0f} seconds")
    print(f"   • Send delay: {APP_CONFIG['min_send_delay_secs']:.0f}-{APP_CONFIG['max_send_delay_secs']:.0f} seconds")
    
    min_hours = APP_CONFIG['min_initiate_hours']
    max_hours = APP_CONFIG.get('max_initiate_hours', min_hours)
    if max_hours > min_hours:
        print(f"   • Initiate after: {min_hours:.1f}-{max_hours:.1f} hours")
    else:
        print(f"   • Initiate after: {min_hours:.1f} hours")
    
    print(f"   • Check interval: {APP_CONFIG['initiation_check_interval_mins']:.0f} minutes")
    print(f"   • OpenAI model: {APP_CONFIG['openai_model']}")
    print(f"   • Known bot IDs: {APP_CONFIG.get('known_bot_ids', [])}")

def get_conversation_topics():
    """Get list of conversation topics for initiation"""
    return [
        "What's everyone's thoughts on the latest market moves?",
        "Any interesting projects you've been following lately?", 
        "How's the DeFi space looking today?",
        "What's your take on the current market sentiment?",
        "Anyone seeing good opportunities right now?",
        "What projects are you most excited about?",
        "How's everyone's portfolio performing?",
        "Any alpha you can share with the group?",
        "What's the most undervalued project right now?",
        "Anyone tried any new protocols recently?",
        "How are you feeling about the current regulatory environment?",
        "Which L2 solutions are you most bullish on?"
    ] 