import discord
from discord.ext import commands
import yt_dlp as youtube_dl  
import sqlite3
import os
from asyncio import Queue

bot = commands.Bot(command_prefix='///', intents = discord.Intents.all())

BOT_TOKEN = os.getenv('BOT_TOKEN')

conn = sqlite3.connect('data/playlists.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS playlists 
             (name TEXT PRIMARY KEY, songs TEXT)''')
conn.commit()

DOWNLOAD_DIR = 'data/downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

song_queue = Queue()

async def play_next(ctx, vc):
    if not song_queue.empty():
        file_path = await song_queue.get()
        vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=file_path), after=lambda e: ctx.bot.loop.create_task(play_next(ctx, vc)))
        await ctx.send(f"Now playing: {os.path.basename(file_path)}")
    else:
        await vc.disconnect()

@bot.command()
async def play(ctx, *, search: str):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    vc = await voice_channel.connect()

    ydl_opts = {
        'format': 'bestaudio/best',
        'ignoreerrors': True,
        'verbose': True,
        'nocheckcertificate': True,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'match_filter': youtube_dl.utils.match_filter_func('!is_live & duration <= 540 & filesize <= 15M'),  # 9 minutes and 15 MB
    }

    if not search.startswith('http'):
        search = f"ytsearch:{search}"

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(search, download=True)
            if 'entries' in info:  
                info = info['entries'][0]
            file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            await song_queue.put(file_path)
            await play_next(ctx, vc)
        except youtube_dl.utils.DownloadError as e:
            await ctx.send(f"An error occurred: {str(e)}")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

@bot.command()
async def playlocal(ctx, file_name: str):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if not os.path.exists(file_path):
        await ctx.send("File not found.")
        return

    vc = await voice_channel.connect()
    vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=file_path), after=lambda e: ctx.bot.loop.create_task(vc.disconnect()))
    await ctx.send(f"Now playing local file: {file_name}")

@bot.command()
async def playlist(ctx, name: str):
    c.execute("INSERT INTO playlists (name, songs) VALUES (?, ?)", (name, ""))
    conn.commit()
    await ctx.send(f"Playlist '{name}' created!")

@bot.command()
async def playlistadd(ctx, name: str, *, search: str):
    c.execute("SELECT songs FROM playlists WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        ydl_opts = {
            'format': 'bestaudio/best',
            'ignoreerrors': True,
            'verbose': True,
            'nocheckcertificate': True,
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'match_filter': youtube_dl.utils.match_filter_func('!is_live & duration <= 540 & filesize <= 15M'),  # 9 minutes and 15 MB
        }

        if not search.startswith('http'):
            search = f"ytsearch:{search}"

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(search, download=True)
                if 'entries' in info:  
                    info = info['entries'][0]
                file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')

                new_songs = row[0] + "," + file_path if row[0] else file_path
                c.execute("UPDATE playlists SET songs=? WHERE name=?", (new_songs, name))
                conn.commit()
                await ctx.send(f"Added song '{info['title']}' to playlist '{name}'!")
            except youtube_dl.utils.DownloadError as e:
                await ctx.send(f"An error occurred: {str(e)}")
            except Exception as e:
                await ctx.send(f"An error occurred: {str(e)}")
    else:
        await ctx.send("Playlist not found!")

@bot.command()
async def playlistshow(ctx, name: str):
    c.execute("SELECT songs FROM playlists WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        songs = row[0].split(',') if row[0] else []
        if songs:
            await ctx.send(f"Playlist '{name}' contains the following songs:\n" + "\n".join([f"{idx + 1}. {os.path.basename(song)}" for idx, song in enumerate(songs)]))
        else:
            await ctx.send(f"Playlist '{name}' is empty.")
    else:
        await ctx.send("Playlist not found!")

@bot.command()
async def playlistplay(ctx, name: str):
    c.execute("SELECT songs FROM playlists WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        voice_channel = ctx.author.voice.channel
        if not voice_channel:
            await ctx.send("You're not in a voice channel!")
            return

        vc = await voice_channel.connect()

        songs = row[0].split(',')
        for song in songs:
            await song_queue.put(song)
        
        await play_next(ctx, vc)
        await ctx.send(f"Playing playlist '{name}'!")
    else:
        await ctx.send("Playlist not found!")

@bot.command()
async def playlistskip(ctx):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    vc = ctx.voice_client
    if not vc or not vc.is_playing():
        await ctx.send("No song is currently playing.")
        return

    members = [member for member in voice_channel.members if not member.bot]
    required_votes = len(members) // 2 + 1
    votes = 0

    def check(reaction, user):
        nonlocal votes
        return user in members and str(reaction.emoji) == '👍'

    message = await ctx.send(f"Vote to skip the current song! {required_votes} votes required.")
    await message.add_reaction('👍')

    try:
        while votes < required_votes:
            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            votes += 1
            if votes >= required_votes:
                await ctx.send("Vote passed! Skipping the song.")
                vc.stop()
                break
    except TimeoutError:
        await ctx.send("Vote timed out. The song will continue playing.")

# End the current playlist
@bot.command()
async def playlistend(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()  
    await song_queue.put(None) 
    await song_queue.join()  
    await ctx.send("Playlist has been ended.")

# List all available commands
@bot.command()
async def commands(ctx):
    cmds = '''
    **Available Commands:**
    - ///play [song name or URL]: Play a song from YouTube.
    - ///playlocal [filename]: Play a local file.
    - ///playlist [playlist name]: Create a new playlist.
    - ///playlistadd [playlist name] [song name or URL]: Add a song to the playlist.
    - ///playlistshow [playlist name]: Show all songs in a playlist.
    - ///playlistplay [playlist name]: Play all songs in a playlist.
    - ///playlistskip: Vote to skip the current song in the playlist.
    - ///playlistend: End the current playlist.
    - ///commands: Show this list of commands.
    '''
    await ctx.send(cmds)
    


bot.run(BOT_TOKEN)
