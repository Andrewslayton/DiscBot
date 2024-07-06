import discord
from discord.ext import commands
import base64
from dotenv import load_dotenv
import os 
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

intents = discord.Intents.default()
intents.messages = True  
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True 
bot = commands.Bot(command_prefix='###', intents=intents)
hangman_game = {}

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True)
    score = Column(Integer, default=0)

engine = create_engine('sqlite:///hangman.db')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)


@bot.command()
async def start(ctx, *, word):
    global hangman_game
    await ctx.message.delete()
    hangman_game[ctx.guild.id] = {
        "word": word.lower(),
        "guessed": [],
        "lives": 6,
        "creator_id": ctx.author.id,
        "current_status": ["X"] * len(word)
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
    creator = game["creator_id"]
    if ctx.author.id == creator:
        await ctx.send("You made the word silly")
        return
    if letter in guessed:
        await ctx.send("You already guessed that letter")
        return
    guessed.append(letter)
    if letter in word:
        await ctx.send("Correct!")
        update_score(ctx.author.id, 10)
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
    for i in range(len(word)):
        if word[i] == letter:
            game["current_status"][i] = letter
    await ctx.send("Current status: " + "".join(game["current_status"]))
    

@bot.command()
async def leaderboard(ctx):
    session = Session()
    all_users = session.query(User).order_by(User.score.desc()).all()
    if not all_users:
        await ctx.send("No scores available.")
    else:
        leaderboard_message = "🏆 Hangman Leaderboard 🏆\n"
        for rank, user in enumerate(all_users, start=1):
            member = ctx.guild.get_member(int(user.discord_id))
            if member:
                username = member.name
            else:
                username = "Unknown User"
            leaderboard_message += f"{rank}. {username} - {user.score} points\n"
        await ctx.send(leaderboard_message)
    session.close()
    
def update_score(discord_id, points):
    session = Session()
    user = session.query(User).filter_by(discord_id=str(discord_id)).first()

    if not user:
        user = User(discord_id=str(discord_id), score=points)
        session.add(user)
    else:
        user.score += points

    session.commit()
    session.close()

bot.run(BOT_TOKEN)

# def check(message):
#     if message.len() == 1:
#         for 


