import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 
from discord import FFmpegPCMAudio

load_dotenv()
TARGET_USER_ID = os.getenv('TARGET_USER_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN3')

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
    audio_source = FFmpegPCMAudio(r'C:\Users\the tank\Downloads\we_lost_the_round.wav')
    voice_client.play(audio_source)
    voice_client.disconnect()
    
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        voice_channel = after.channel
        if voice_channel is not None:
            if voice_channel.guild.voice_client is not None:
                await voice_channel.guild.voice_client.disconnect()
            voice_client = await voice_channel.connect()
            audio_source = FFmpegPCMAudio(r'C:\Users\the tank\Downloads\we_lost_the_round.wav')
            voice_client.play(audio_source)
            voice_client.disconnect()

bot.run(BOT_TOKEN)