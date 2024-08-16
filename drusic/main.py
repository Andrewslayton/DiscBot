import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import sqlite3
import os
from asyncio import Queue
import yt_dlp as youtube_dl  
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from YTDL import YTDLSource 

bot = commands.Bot(command_prefix='d/', intents=discord.Intents.all())


load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
SPOTIFY_TOKEN = os.getenv('SPOTIFY_TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_TOKEN))

conn = sqlite3.connect('data/playlists.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS playlists 
             (name TEXT PRIMARY KEY, songs TEXT)''')
conn.commit()

DOWNLOAD_DIR = 'data/downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

song_queue = Queue()

@bot.command()
async def help(ctx):
    help = '''
    common problems (you guys are going to give me a headache i already know)
    -once all songs are concluded and bots dont already connected do d/playlistend
    -if bot is being "weird" hit it with d/playlistend and then leave it be for a few minutes
    -playlists take a long time to download and i will remove ability to make playlists for people who abuse it
    -if all else fails ping me 
    '
    '''
    await ctx.send(help)

@bot.command()
async def commands(ctx):
    cmds = '''
    **Available Commands:**
    - d/play [song name or URL]: Play a song, accepts spotify playlist links youtube playlist links and soundcloud playlist link. Upon no link will search youtube.
    - d/playlist [playlist name]: Create a new playlist.
    - d/playlistadd [playlist name] [song name or URL]: Add a song to the playlist.
    - d/playlistshow [playlist name]: Show all songs in a playlist.
    - d/playlistplay [playlist name]: Play all songs in a playlist.
    - d/playlistskip: Vote to skip the current song in the playlist.
    - d/playlistend: End the current playlist.
    - d/help
    - d/commands: Show this list of commands.
    '''
    await ctx.send(cmds)

async def play_next(ctx, vc):
    if not vc.is_connected(): 
        return
    if not song_queue.empty():
        source = await song_queue.get()

        def after_playing(error):
            coro = play_next(ctx, vc)
            fut = asyncio.run_coroutine_threadsafe(coro, ctx.bot.loop)
            try:
                fut.result()
            except Exception as exc:
                print(f'Error in after_playing: {exc}')

        vc.play(source, after=after_playing)
        await ctx.send(f"Now playing: {source.title}")
    else:
        await asyncio.sleep(10)
        if song_queue.empty() and not vc.is_connected():
            await vc.disconnect()

@bot.command()
async def play(ctx, *, search: str):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    if ctx.voice_client is None:
        vc = await voice_channel.connect()
    else:
        vc = ctx.voice_client
        if vc.channel != voice_channel:
            await vc.move_to(voice_channel)

    if "spotify.com" in search:
        await spotifyplay(ctx, search)
    elif "soundcloud.com" in search:
        await soundcloudplay(ctx, search)
    else:
        sources = await YTDLSource.create_source(search, loop=bot.loop)
    
        for source in sources:
            await song_queue.put(source)
            if not vc.is_playing():
                await play_next(ctx, vc)


@bot.command()
async def playlist(ctx, name: str):
    c.execute("INSERT INTO playlists (name, songs) VALUES (?, ?)", (name, ""))
    conn.commit()
    await ctx.send(f"Playlist '{name}' created!")

@bot.command()
async def playlistend(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()  # Stop the current song

    # Clear the song queue completely
    while not song_queue.empty():
        song_queue.get_nowait()  # Remove all songs from the queue

    # Disconnect the bot from the voice channel
    if vc and vc.is_connected():
        await vc.disconnect()

    await ctx.send("Playlist has been ended")
    
@bot.command()
async def playlistadd(ctx, name: str, *, search: str):
    c.execute("SELECT songs FROM playlists WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        max_filesize = 15 * 1024 * 1024  # 15 MB limit

        ydl_opts = {
            'format': 'bestaudio/best',
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'match_filter': youtube_dl.utils.match_filter_func(f"filesize <= {max_filesize}"),
            'default_search': 'ytsearch',  # Enables YouTube search if a direct URL is not provided
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search, download=True)
            if not info:
                await ctx.send(f"Could not find any results for {search}.")
                return

            if 'entries' in info:  
                entries = info['entries']
            else: 
                entries = [info]

            for entry in entries:
                file_path = os.path.join(DOWNLOAD_DIR, f"{entry['title']}.mp3")
                new_songs = row[0] + "," + file_path if row[0] else file_path
                c.execute("UPDATE playlists SET songs=? WHERE name=?", (new_songs, name))
                conn.commit()

                await ctx.send(f"Added '{entry['title']}' to playlist '{name}'!")
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
            audio_source = discord.FFmpegPCMAudio(song)
            await song_queue.put(audio_source)
        
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
    except asyncio.TimeoutError:
        await ctx.send("Vote timed out. The song will continue playing.")

@bot.command()
async def spotifyplay(ctx, link: str):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    vc = ctx.voice_client
    if vc is None:
        vc = await voice_channel.connect()
        
    if "track" in link:
        track_id = link.split("/")[-1].split("?")[0]
        track = spotify.track(track_id)
        track_name = track['name']
        artists = ', '.join([artist['name'] for artist in track['artists']])
        search_query = f"{track_name} {artists}"

        sources = await YTDLSource.create_source(search_query, loop=bot.loop)
        for source in sources:
            await song_queue.put(source)
            await play_next(ctx, vc)

    elif "album" in link:
        album_id = link.split("/")[-1].split("?")[0]
        results = spotify.album_tracks(album_id)
        tracks = results['items']

        async def download_and_play_track(track_item):
            track = track_item
            track_name = track['name']
            artists = ', '.join([artist['name'] for artist in track['artists']])
            search_query = f"{track_name} {artists}"

            sources = await YTDLSource.create_source(search_query, loop=bot.loop)
            for source in sources:
                await song_queue.put(source)
                if not vc.is_playing(): 
                    await play_next(ctx, vc)
                while vc.is_playing():
                    await asyncio.sleep(1)


        for item in tracks:
            await download_and_play_track(item)
            
    elif "playlist" in link:
        playlist_id = link.split("/")[-1].split("?")[0]
        results = spotify.playlist_tracks(playlist_id)
        tracks = results['items']

        async def download_and_play_track(track_item):
            track = track_item['track']
            track_name = track['name']
            artists = ', '.join([artist['name'] for artist in track['artists']])
            search_query = f"{track_name} {artists}"

            sources = await YTDLSource.create_source(search_query, loop=bot.loop)
            for source in sources:
                await song_queue.put(source)
                if not vc.is_playing(): 
                    await play_next(ctx, vc)
                while vc.is_playing():
                    await asyncio.sleep(1)

        for item in tracks:
            await download_and_play_track(item)

@bot.command()
async def soundcloudplay(ctx, playlist_url: str):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    vc = ctx.voice_client
    if vc is None:
        vc = await voice_channel.connect()

    ydl_opts = {
        'format': 'bestaudio/best',
        'ignoreerrors': True,
        'nocheckcertificate': True,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

            async def download_and_play_track(track_info):
                try:
                    stream_url = track_info['url']
                    vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=stream_url))
                    await ctx.send(f"Now streaming SoundCloud track: {track_info['title']}")

                    while vc.is_playing():
                        await asyncio.sleep(1)

                    info = ydl.extract_info(track_info['webpage_url'], download=True)
                    file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
                    await song_queue.put(file_path)
                    await play_next(ctx, vc)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    await ctx.send(f"Downloaded and played: {track_info['title']}")
                except youtube_dl.utils.DownloadError as e:
                    await ctx.send(f"An error occurred while downloading '{track_info['title']}': {str(e)}")
                except Exception as e:
                    await ctx.send(f"An error occurred: {str(e)}")

            if 'entries' in info:
                for track_info in info['entries']:
                    await download_and_play_track(track_info)
            else:
                await download_and_play_track(info)

    except youtube_dl.utils.DownloadError as e:
        await ctx.send(f"An error occurred: {str(e)}")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

bot.run(BOT_TOKEN)
