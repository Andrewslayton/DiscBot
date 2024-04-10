
# This is a simple bot that plays a YouTube link when a user joins or leaves a channel. please use the cloud if your friends decide to link bomb you or have a large server.

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
bot = commands.Bot(command_prefix='!!!', intents=intents)

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
        outro TEXT
    )
''')
conn.commit()
# c.execute('ALTER TABLE user_links ADD COLUMN outro TEXT') you wont need this if you download the code
# conn.commit()
@bot.command()
async def intro(ctx, link: str):
    """Set the user's YouTube link."""
    c.execute('INSERT OR REPLACE INTO user_links VALUES (?, ?)', (ctx.author.id, link))
    conn.commit()
    await ctx.send(f"Intro set for {ctx.author.name}!")
@bot.command()
async def outro(ctx, link: str):
    """Set the user's YouTube outro."""
    c.execute('UPDATE user_links SET outro = ? WHERE user_id = ?', (link, ctx.author.id))
    conn.commit()
    await ctx.send(f"Outro set for {ctx.author.name}!")

@bot.event
async def on_voice_state_update(member, before, after):
    """Play the user's YouTube link when they join a voice channel."""
    c.execute('SELECT link FROM user_links WHERE user_id = ?', (member.id,))
    link = c.fetchone()
    c.execute('SELECT outro FROM user_links WHERE user_id = ?', (member.id,))
    outro = c.fetchone()
    if link is not None or outro is not None:
        if before.channel is None and after.channel is not None and link is not None:  # User joined a voice channel
            voice_channel = after.channel
        elif before.channel is not None and after.channel is None and outro is not None: 
            voice_channel = before.channel
        else:
            return
        voice_client = await voice_channel.connect()
        yt = YouTube(outro[0])
        stream = yt.streams.filter(only_audio=True).first()
        filename = stream.default_filename
        stream.download(filename=filename)
        voice_client.play(discord.FFmpegPCMAudio(filename))
        while voice_client.is_playing():
            await asyncio.sleep(1)
        await voice_client.disconnect()
        os.remove(filename)

bot.run(BOT_TOKEN)