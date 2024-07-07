
# This is a simple bot that plays a YouTube link when a user joins or leaves a channel. please use the cloud if your friends decide to link bomb you or have a large server.

import asyncio
import sqlite3
from discord.ext import commands
from discord import FFmpegPCMAudio, Intents
from yt_dlp import YoutubeDL
import discord
from dotenv import load_dotenv
import os
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

# Ensure the user_links table exists
c.execute('''
    CREATE TABLE IF NOT EXISTS user_links (
        user_id INTEGER PRIMARY KEY,
        link TEXT,
        outro TEXT
    )
''')

# Add the 'outro' column if it does not exist
try:
    c.execute('ALTER TABLE user_links ADD COLUMN outro TEXT')
except sqlite3.OperationalError:
    # The column already exists, so we can ignore this error
    pass

conn.commit()

@bot.command()
async def intro(ctx, link: str):
    """Set the user's YouTube link."""
    c.execute('INSERT OR REPLACE INTO user_links (user_id, link, outro) VALUES (?, ?, (SELECT outro FROM user_links WHERE user_id = ?))', (ctx.author.id, link, ctx.author.id))
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
    """Play the user's YouTube link when they join or leave a voice channel."""
    c.execute('SELECT link FROM user_links WHERE user_id = ?', (member.id,))
    link = c.fetchone()
    c.execute('SELECT outro FROM user_links WHERE user_id = ?', (member.id,))
    outro = c.fetchone()

    play_link = None

    if link and before.channel is None and after.channel is not None:  # User joined a voice channel
        play_link = link[0]
        voice_channel = after.channel
    elif outro and before.channel is not None and after.channel is None:  # User left a voice channel
        play_link = outro[0]
        voice_channel = before.channel

    if play_link:
        try:
            voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
            voice_client = await voice_channel.connect()
            yt = YouTube(play_link)
            stream = yt.streams.filter(only_audio=True).first()
            filename = stream.default_filename
            stream.download(filename=filename)
            voice_client.play(discord.FFmpegPCMAudio(filename))
            while voice_client.is_playing():
                await asyncio.sleep(1)
            await voice_client.disconnect()
            os.remove(filename)
        except Exception as e:
            print(f"Failed to connect or play audio: {e}")

bot.run(BOT_TOKEN)