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
hangman_game = {}


@bot.command()
async def start(ctx, *, word):
    global hangman_game
    await ctx.message.delete()
    hangman_game[ctx.guild.id] = {
        "word": word.lower(),
        "guessed": [],
        "lives": 6
    }
    length = len(word)
    await ctx.send("Welcome to Hangman! The word is " + str(length) + " letters long" + ". Guess a letter by typing #guess <letter>")

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command()
async def guess(ctx, *, letter):
    await ctx.send("You guessed " + letter)
    letter = letter.lower()
    if ctx.guild.id not in hangman_game:
        await ctx.send("You need to start a game first!")
        return
    if len(letter) != 1:
        await ctx.send("You got problems, only one letter no cheating")
        return
    game = hangman_game[ctx.guild.id]
    word = game["word"]
    guessed = game["guessed"]
    lives = game["lives"]
    if letter in guessed:
        await ctx.send("You already guessed that letter")
        return
    guessed.append(letter)
    if letter in word:
        await ctx.send("Correct!")
    else:
        await ctx.send("Wrong!")
        lives -= 1
        game["lives"] = lives
    await ctx.send("You have " + str(lives) + " lives left")
    if lives <= 0:
        await ctx.send("You lost! The word was " + word)
        del hangman_game[ctx.guild.id]
        return
    if all(letter in guessed for letter in word):
        await ctx.send("You won! The word was " + word)
        del hangman_game[ctx.guild.id]
        return
bot.run(BOT_TOKEN)

# def check(message):
#     if message.len() == 1:
#         for 


