import os

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

WAVELINK_URI = os.environ.get('WAVELINK_URI')
WAVELINK_PASSWORD = os.environ.get('WAVELINK_PASSWORD')

DATABASE_URL=os.environ.get('DATABASE_URL')

DISCORD_VOICE_CHANNELS_ID = os.environ.get('DISCORD_VOICE_CHANNELS_ID')

if __name__ == '__main__':
    pass
