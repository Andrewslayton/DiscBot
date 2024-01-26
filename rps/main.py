import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 
import random 

load_dotenv()
TARGET_USER_ID = os.getenv('TARGET_USER_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN')

intents = discord.Intents.default()
intents.messages = True  
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)
choise = ""

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command()
async def rps(ctx, *, choice):
    if choise.lower() != "rock" or choise.lower() != "paper" or choise.lower() != "scissors":
        await ctx.send("Please choose either rock, paper, or scissors")
        return
    await ctx.message.delete()
    global choise
    choise = choice.lower()
   
@bot.command()
async def guess (ctx, *, letter):
    if letter.lower() != "rock" or letter.lower() != "paper" or letter.lower() != "scissors":
        await ctx.send("Please choose either rock, paper, or scissors")
        return
    await ctx.message.delete()
    letter = letter.lower()
    if letter == "rock " and choise == "scissors":
        await ctx.send("You win")
    elif letter == "rock" and choise == "paper":
        await ctx.send("You lose")
    elif letter == "paper" and choise == "rock":
        await ctx.send("You win")
    elif letter == "paper" and choise == "scissors":
        await ctx.send("You lose")
    elif letter == "scissors" and choise == "paper":
        await ctx.send("You win")
    elif letter == "scissors" and choise == "rock":
        await ctx.send("You lose")
    elif letter == choise:
        await ctx.send("It's a tie")
    else:
        await ctx.send("Something went wrong")

bot.run(BOT_TOKEN)