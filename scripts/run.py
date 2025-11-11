#!/usr/bin/env python3
"""
Launcher script for CatGirl Discord Bot
Handles startup, error recovery, and graceful shutdown
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def check_requirements():
    """Check if all required files exist"""
    required_files = [
        'bot.py',
        'waifu_api.py', 
        'config.py',
        '.env'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        if '.env' in missing_files:
            logger.error("❌ Файл .env не найден!")
            logger.info("📝 Скопируйте .env.example в .env и заполните настройки:")
            logger.info("   cp .env.example .env")
            return False
        else:
            logger.error(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
            return False
    
    return True

async def main():
    """Main function to run the bot"""
    logger.info("🚀 Запуск CatGirl Discord Bot...")
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Import bot after checking requirements
    try:
        from bot import bot
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        logger.info("💡 Убедитесь, что установлены все зависимости: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Ошибка конфигурации: {e}")
        sys.exit(1)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"📡 Получен сигнал {signum}, завершение работы...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run bot with error handling
    try:
        await bot.start(bot.http.token)
    except discord.LoginFailure:
        logger.error("❌ Неверный токен Discord!")
        logger.info("💡 Проверьте DISCORD_TOKEN в файле .env")
    except discord.HTTPException as e:
        logger.error(f"❌ HTTP ошибка Discord: {e}")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
    finally:
        logger.info("👋 Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
