#!/usr/bin/env python3
"""
Simple Telegram Bot - Main Entry Point

This is the main entry point for the simple telegram bot.
The bot logic is contained in simple_bot.py.
"""

import asyncio
import traceback
from src.simple_bot import SimpleTelegramBot

async def main():
    """Main entry point for the Simple Telegram Bot"""
    print("🚀 Starting Simple Telegram Bot...")
    
    bot = SimpleTelegramBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        traceback.print_exc()
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main()) 