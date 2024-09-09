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
import requests
import lyricsgenius
import re
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from discord.ui import Button, View
from YTDL import YTDLSource 

bot = commands.Bot(command_prefix='d/', intents=discord.Intents.all())


load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
SPOTIFY_TOKEN = os.getenv('SPOTIFY_TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
GENIUS_API_KEY = os.getenv('GENIUS_TOKEN')
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_TOKEN))
genius = lyricsgenius.Genius(GENIUS_API_KEY, skip_non_songs=True, excluded_terms=["(Remix)", "(Live)"], remove_section_headers=True)
conn = sqlite3.connect('data/playlists.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS playlists 
             (name TEXT PRIMARY KEY, songs TEXT)''')
conn.commit()

DOWNLOAD_DIR = 'data/downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

song_queue = Queue()
current_song = None
current_artist = None
looping = False
@bot.command()
async def issue(ctx):
    issue = '''
    common problems (you guys are going to give me a headache i already know)
    -once all songs are concluded and bots dont already connected do d/playlistend
    -if bot is being "weird" hit it with d/playlistend and then leave it be for a few minutes
    -playlists take a long time to download and i will remove ability to make playlists for people who abuse it
    -if all else fails ping me 
    '
    '''
    await ctx.send(issue)

@bot.command()
async def commands(ctx):
    cmds = '''
    **Available Commands:**
    - d/p [song name or URL]: Play a song, accepts spotify playlist links youtube playlist links and soundcloud playlist link. Upon no link will search youtube.
    - d/playlist [playlist name]: Create a new playlist.
    - d/playlistadd [playlist name] [song name or URL]: Add a song to the playlist.
    - d/playlistshow [playlist name]: Show all songs in a playlist.
    - d/playlistplay [playlist name]: Play all songs in a playlist.
    - d/s: Vote to skip the current song in the playlist.
    - d/loop : loops current song until called again
    - d/end: End the current playlist.
    - d/issue: issue help
    - d/commands: Show this list of commands.
    '''
    await ctx.send(cmds)
    
async def play_next(ctx, vc):
    global looping

    if not vc.is_connected():
        return

    if not song_queue.empty():
        source = await song_queue.get()
        await ctx.send(f'queue size {song_queue.qsize()}')
        def after_playing(error):
            coro = play_next(ctx, vc)
            fut = asyncio.run_coroutine_threadsafe(coro, ctx.bot.loop)
            try:
                fut.result()
            except Exception as exc:
                print(f'Error in after_playing: {exc}')
                

        vc.play(source, after=after_playing)
        artist_name, song_title = extract_artist_and_title(source.title)
        if not artist_name:
            artist_name = source.data.get('uploader')
        track_length = source.duration
        formatted_length = f"{divmod(track_length, 60)[0]}:{divmod(track_length, 60)[1]:02d}" if track_length else "Unknown length"

        sources = await YTDLSource.create_source(current_song, loop=bot.loop)
        if looping and song_queue.qsize() < 2:
            for source in sources:
                await song_queue.put(source)
                
        embed = discord.Embed(title="Now Playing", color=discord.Color.blue())
        embed.add_field(name="Song", value=song_title, inline=False)
        embed.add_field(name="Artist", value=artist_name, inline=False)
        embed.add_field(name="Duration", value=formatted_length, inline=False)
        
        async def loop_button_callback(interaction):
            global looping
            looping = not looping
            status = "enabled" if looping else "disabled"
            await interaction.response.send_message(f"Looping {status}.", ephemeral=True)
        
        async def lyrics_button_callback(interaction):
            global current_song, current_artist
            if current_song is None or current_artist is None:
                await ctx.send("No song is currently playing.")
                return
            lyrics_text = await get_lyrics(current_song, current_artist)
            if lyrics_text:
                embed = discord.Embed(title=f"Lyrics for {current_song} by {current_artist}", color=discord.Color.purple())
                chunks = [lyrics_text[i:i + 1024] for i in range(0, len(lyrics_text), 1024)] 

                for i, chunk in enumerate(chunks):
                    embed.add_field(name=f"Lyrics (Part {i + 1})", value=chunk, inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Sorry, no lyrics were found for **{current_song}** by **{current_artist}**.")
                
        async def skip_button_callback(interaction):
            vc.stop()
            await interaction.response.send_message("fine we can skip")
        
        loop_button = Button(label = "Loop", style = discord.ButtonStyle.green)
        loop_button.callback = loop_button_callback
        
        skip_button = Button(label = "Skip", style = discord.ButtonStyle.red)
        skip_button.callback = skip_button_callback
        
        lyrics_button = Button(label = "Lyrics", style = discord.ButtonStyle.blurple)
        lyrics_button.callback = lyrics_button_callback
        
        view = View()
        view.add_item(loop_button)
        view.add_item(skip_button)
        view.add_item(lyrics_button)
        await ctx.send(embed=embed, view=view)

    else:
        await asyncio.sleep(10)
        if song_queue.empty() and vc.is_connected():
            await vc.disconnect()
            await ctx.send("No more tracks. Disconnecting...")

@bot.command()
async def p(ctx, *, search: str):
    global current_song, current_artist

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
    
    sources = await YTDLSource.create_source(search, loop=bot.loop)

    for source in sources:
        track_length = source.duration
        if track_length:
            minutes, seconds = divmod(track_length, 60)
            formatted_length = f"{minutes}:{seconds:02d}"
        else:
            formatted_length = "Unknown length"
        await song_queue.put(source)
        current_song = source.title 
        current_artist = source.data.get('uploader')

        if not vc.is_playing():
            await play_next(ctx, vc)

@bot.command()
async def loop(ctx):
    global current_song, current_artist, looping
    vc = ctx.voice_client
    if vc is None or not vc.is_connected():
        await ctx.send("Bot is not connected to a voice channel.")
        return
    looping = not looping
    if looping:
        await ctx.send("looping enabled")
    else:
        await ctx.send("looping turned off")


def clean_title(title):
    cleaned_title = re.sub(r'\(.*?\)', '', title)
    cleaned_title = re.sub(r'#\S+', '', cleaned_title)
    cleaned_title = re.sub(r'(feat\.|ft\.).*', '', cleaned_title, flags=re.I)
    cleaned_title = re.sub(r'[-,]+', ' ', cleaned_title).strip()
    return cleaned_title.strip()

def extract_artist_and_title(title):
    separators = [' x ', ' ft. ', ' feat. ', ' - ']
    for sep in separators:
        if sep in title:
            parts = title.split(sep, 1)
            artist_name = parts[0].strip()
            song_title = clean_title(parts[1])
            return artist_name, song_title

    artist_name = None
    song_title = clean_title(title)
    return artist_name, song_title

async def find_best_match(artist_name, target_song_title):
    try:
        print(f"Searching for: {artist_name} - {target_song_title}")
        song = genius.search_song(target_song_title, artist_name)
        if song:
            return song.lyrics  
        else:
            print("No exact match found.")
        return None  
    except Exception as e:
        print(f"Error finding best match: {e}")
        return None

async def get_lyrics(track_name, artist_name):
    try:
        cleaned_track_name = clean_title(track_name)
        lyrics = await find_best_match(artist_name, cleaned_track_name)
        return lyrics if lyrics else None
    except Exception as e:
        return None

@bot.command()
async def lyrics(ctx):
    global current_song, current_artist
    if current_song is None or current_artist is None:
        await ctx.send("No song is currently playing.")
        return

    lyrics_text = await get_lyrics(current_song, current_artist)

    if lyrics_text:
        embed = discord.Embed(title=f"Lyrics for {current_song} by {current_artist}", color=discord.Color.purple())
        chunks = [lyrics_text[i:i + 1024] for i in range(0, len(lyrics_text), 1024)] 

        for i, chunk in enumerate(chunks):
            embed.add_field(name=f"Lyrics (Part {i + 1})", value=chunk, inline=False)

        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Sorry, no lyrics were found for **{current_song}** by **{current_artist}**.")
        
@bot.command()
async def playlist(ctx, name: str):
    c.execute("INSERT INTO playlists (name, songs) VALUES (?, ?)", (name, ""))
    conn.commit()
    await ctx.send(f"Playlist '{name}' created!")

@bot.command()
async def end(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()  # Stop the current song
    while not song_queue.empty():
        song_queue.get_nowait() 
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
        if ctx.voice_client is None:
            vc = await voice_channel.connect()
        else:
            vc = ctx.voice_client
        if vc.channel != voice_channel:
            await vc.move_to(voice_channel)
        songs = row[0].split(',')
        for song in songs:
            audio_source = discord.FFmpegPCMAudio(song)
            await song_queue.put(audio_source)
        
        await play_next(ctx, vc)
        await ctx.send(f"Playing playlist '{name}'!")
    else:
        await ctx.send("Playlist not found!")


@bot.command()
async def skip(ctx):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You're not in a voice channel!")
        return

    vc = ctx.voice_client
    if not vc or not vc.is_playing():
        await ctx.send("No song is currently playing.")
        return

    message = await ctx.send(f"skipping song")
    try:
        vc.stop()
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
