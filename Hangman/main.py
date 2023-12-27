import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN2')

intents = discord.Intents.default()
intents.messages = True  
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True 
bot = commands.Bot(command_prefix='#', intents=intents)


@bot.command()
async def start(ctx, *, word):
    await ctx.message.delete()
    length = len(word)
    await ctx.send("Welcome to Hangman! The word is " + str(length) + " letters long" + ". Guess a letter by typing #guess <letter>")

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


bot.run(BOT_TOKEN)

# def check(message):
#     if message.len() == 1:
#         for 


