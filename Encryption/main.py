import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 

load_dotenv()
TARGET_USER_ID = os.getenv('TARGET_USER_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN')

bot = commands.Bot(command_prefix='!')

def encrypt(message):
    return base64.b64encode(message.encode('utf-8'))


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.event 
async def if_message(message):
    if message.author.id == int(TARGET_USER_ID):
        try:
            await message.delete()
        except:
            discord.errors.Forbidden
            await message.channel.send("I cannot ovveride ardi he too powerful")
        await message.channel.send("Ardi the stink Albanian says :")
        await message.channel.send(encrypt(message.content))

    await bot.process_commands(message)
    
bot.run(BOT_TOKEN)

