import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 

TARGET_USER_ID = os.getenv('TARGET_USER_ID')

BOT_TOKEN = os.getenv('BOT_TOKEN')

bot = commands.Bot(command_prefix='!')

