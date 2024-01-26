import asyncio
import sqlite3
from discord.ext import commands
from discord import FFmpegPCMAudio, Intents
from yt_dlp import YoutubeDL
import discord
from dotenv import load_dotenv
import os
import youtube_dl
from pytube import YouTube

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN4')

intents = discord.Intents.default()
intents.messages = True  
intents.guilds = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

ydl_opts = {
    'format': 'bestaudio',
    'ignoreerrors': True,
    'verbose': True
}

conn = sqlite3.connect('user_links.db')
c = conn.cursor()

c.execute('SELECT * FROM user_links')
rows = c.fetchall()

for row in rows:
    print(row)

conn = sqlite3.connect('user_links.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS user_links (
        user_id INTEGER PRIMARY KEY,
        link TEXT
    )
''')
conn.commit()

@bot.command()
async def intro(ctx, link: str):
    """Set the user's YouTube link."""
    c.execute('INSERT OR REPLACE INTO user_links VALUES (?, ?)', (ctx.author.id, link))
    conn.commit()
    await ctx.send(f"Intro set for {ctx.author.name}!")

@bot.event
async def on_voice_state_update(member, before, after):
    """Play the user's YouTube link when they join a voice channel."""
    c.execute('SELECT link FROM user_links WHERE user_id = ?', (member.id,))
    link = c.fetchone()
    if link is not None and before.channel is None and after.channel is not None:
        voice_channel = after.channel
        voice_client = await voice_channel.connect()
        yt = YouTube(link[0])
        stream = yt.streams.filter(only_audio=True).first()
        filename = stream.default_filename
        stream.download(filename=filename)
        voice_client.play(discord.FFmpegPCMAudio(filename))
        while voice_client.is_playing():
            await asyncio.sleep(1)
        await voice_client.disconnect()
        os.remove(filename)

bot.run(BOT_TOKEN)