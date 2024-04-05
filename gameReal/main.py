import random
import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 
from discord import FFmpegPCMAudio
import Time

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN5')

intents = discord.Intents.default()
intents.messages = True  
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True 
bot = commands.Bot(command_prefix='', intents=intents)
time = Time()
random.seed(time)


@bot.event()
async def screenshot(ctx,):
    