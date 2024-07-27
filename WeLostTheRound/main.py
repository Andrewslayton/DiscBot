import discord
import asyncio
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 
from discord import FFmpegPCMAudio

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

intents = discord.Intents.default()
intents.messages = True  
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True 
bot = commands.Bot(command_prefix='', intents=intents)



@bot.command()
async def lost(ctx,):
    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()
    voice_client = await voice_channel.connect()
    audio_source = FFmpegPCMAudio(r'we_lost_the_round.wav')
    voice_client.play(audio_source)
    while voice_client.is_playing():
        await asyncio.sleep(1)
    await voice_client.disconnect()
    

bot.run(BOT_TOKEN)