import discord
from discord.ext import commands, tasks
import steamspypi
import random
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN5')

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True
bot = commands.Bot(command_prefix='..', intents=intents)

def get_top_games_by_genre(tag):
    data_request = {
        'request': 'tag',
        'tag': tag
    }
    data = steamspypi.download(data_request)
    if data:
        top_games = data
        return top_games
    else:
        return None

@bot.command()
async def vote(ctx, *, genre: str):
    top_games = get_top_games_by_genre(genre)
    if top_games:
        try:
            random_game = random.choice(list(top_games.values()))
            game_name = random_game['name']
            app_id = random_game['appid']
            game_link = f"https://store.steampowered.com/app/{app_id}"
            await ctx.send(f"Vote for {game_name}: {game_link}")
        except Exception as e:
            print("Error:", e)
            await ctx.send("An error occurred while selecting a random game.")
    else:
        await ctx.send("No games found for the specified genre.")

@tasks.loop(hours = 24)
async def ask_for_genre():
    for guild in bot.guilds:
        channel = discord.utils.get(guild.channels , name='gameofday')
        if not channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            channel = await guild.create_text_channel('gameofday', overwrites=overwrites)
        await channel.send("Please enter a genre for today's game vote.")

@ask_for_genre.before_loop
async def before_ask_for_genre():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    ask_for_genre.start()


@bot.command()
async def genres(ctx):
    genres = [
        "Action", "Adventure", "Casual", "Indie", "Massively Multiplayer",
        "Racing", "RPG", "Simulation", "Sports", "Strategy",
        "Horror", "Puzzle", "Arcade", "Platformer", "Visual Novel",
        "Survival", "Open World", "Fantasy", "Sci-fi", "Historical",
        "Stealth", "Fighting", "Shooter", "Exploration", "Point & Click",
        "Music", "Educational", "Card Game", "Tower Defense", "War",
        "Mystery", "Hack and Slash", "Battle Royale", "Tactical",
        "Rogue-lite", "Metroidvania", "Life Simulation", "City Builder",
        "Noir", "Western", "Cyberpunk", "Space", "Superhero",
        "Military", "Anime", "Zombies", "Voxel", "Pixel Graphics",
        "Cyberpunk", "Survival Horror", "Post-apocalyptic", "Fantasy",
        "Mystery Dungeon", "Time Travel", "Space Exploration", "Aliens",
        "Lovecraftian", "Dystopian", "Alternate History", "Medieval",
        "Mythology", "Gothic", "Crime", "Psychological Horror", "Dinosaurs",
        "Sandbox", "Trading Card Game", "Swordplay", "RTS", "Turn-Based",
        "Logic", "Naval", "Naval Combat", "Economy", "Political",
        "Competitive", "Sailing", "Exploration", "Tower Climbing", "Cooking",
        "Magic", "Mythical Creatures", "Dragons", "Vikings", "Samurai",
        "Ninjas", "Hacking", "Espionage", "Martial Arts", "Space Opera",
        "J-RPG", "MMO", "Real-Time", "Real-Time Tactics", "Time Management",
        "Trading", "Economic", "Investigation", "Episodic", "Post-Post-Apocalyptic",
        "Survival Crafting", "Grand Strategy", "Political Simulation", "Naval Battles",
        "Space Sim", "Space Combat", "Hacking", "Espionage", "Martial Arts",
        "Space Opera", "J-RPG", "MMO", "Real-Time", "Real-Time Tactics",
        "Time Management", "Trading", "Economic", "Investigation", "Episodic",
        "Post-Post-Apocalyptic", "Survival Crafting", "Grand Strategy",
        "Political Simulation", "Naval Battles", "Space Sim", "Space Combat"
    ]
    await ctx.send("Available genres: " + ", ".join(genres))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.name == 'GAMEOFDAY':
        genre = message.content.strip()
        top_games = get_top_games_by_genre(genre)
        if top_games:
            random_game = random.choice(list(top_games.values()))
            game_name = random_game['name']
            app_id = random_game['appid']
            game_link = f"https://store.steampowered.com/app/{app_id}"
            await message.channel.send(f"Vote for {game_name}: {game_link}")
        else:
            await message.channel.send("No games found for the specified genre.")
    await bot.process_commands(message)

bot.run(BOT_TOKEN)