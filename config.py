import os
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WAIFU_API_TOKEN = os.getenv('WAIFU_API_TOKEN')

# API URLs
WAIFU_API_BASE_URL = 'https://api.waifu.im'

# Bot settings
COMMAND_PREFIX = '!'
MAX_IMAGES_PER_REQUEST = 5

# Note: Tags are now loaded dynamically from the Waifu.im API
# The bot will automatically fetch all available tags on startup
# Fallback tags are defined in bot.py if API is unavailable
