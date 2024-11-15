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
import functools
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
    global looping, current_song, current_artist

    if not vc.is_connected():
        return

    if not song_queue.empty() or looping:
        if not looping:
            source = await song_queue.get()
        else:
            # Reuse the current source for looping
            source = vc.source
            if source is None:
                source = await song_queue.get()

        def after_playing(error):
            coro = play_next(ctx, vc)
            fut = asyncio.run_coroutine_threadsafe(coro, ctx.bot.loop)
            try:
                fut.result()
            except Exception as exc:
                print(f'Error in after_playing: {exc}')

        vc.play(source, after=after_playing)

        # Update current song and artist
        current_song = getattr(source, 'title', 'Unknown')
        current_artist = getattr(source, 'data', {}).get('uploader', 'Unknown')

        # Extract artist and title for display
        artist_name, song_title = extract_artist_and_title(current_song)
        if not artist_name:
            artist_name = current_artist

        # Get track length and format it correctly
        track_length = getattr(source, 'duration', None)
        if track_length:
            minutes, seconds = divmod(track_length, 60)
            minutes = int(minutes)
            seconds = int(seconds)
            formatted_length = f"{minutes}:{seconds:02d}"
        else:
            formatted_length = "Unknown length"

        # Prepare embed
        embed = discord.Embed(title="Now Playing", color=discord.Color.blue())
        embed.add_field(name="Song", value=song_title, inline=False)
        embed.add_field(name="Artist", value=artist_name, inline=False)
        embed.add_field(name="Duration", value=formatted_length, inline=False)

        # Define button callbacks
        async def loop_button_callback(interaction):
            global looping
            looping = not looping
            status = "enabled" if looping else "disabled"
            await interaction.response.send_message(f"Looping {status}.", ephemeral=True)

        async def lyrics_button_callback(interaction):
            if current_song is None or current_artist is None:
                await interaction.response.send_message("No song is currently playing.", ephemeral=True)
                return
            lyrics_text = await get_lyrics(current_song, current_artist)
            if lyrics_text:
                lyrics_embed = discord.Embed(
                    title=f"Lyrics for {current_song} by {current_artist}",
                    color=discord.Color.purple()
                )
                chunks = [lyrics_text[i:i + 1024] for i in range(0, len(lyrics_text), 1024)]
                for i, chunk in enumerate(chunks):
                    lyrics_embed.add_field(name=f"Lyrics (Part {i + 1})", value=chunk, inline=False)
                await interaction.response.send_message(embed=lyrics_embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"Sorry, no lyrics were found for **{current_song}** by **{current_artist}**.",
                    ephemeral=True
                )

        async def skip_button_callback(interaction):
            if vc.is_playing():
                vc.stop()
                await interaction.response.send_message("Skipped the current song.", ephemeral=True)
            else:
                await interaction.response.send_message("No song is currently playing.", ephemeral=True)

        # Create buttons
        loop_button = Button(label="Loop", style=discord.ButtonStyle.green)
        loop_button.callback = loop_button_callback

        skip_button = Button(label="Skip", style=discord.ButtonStyle.red)
        skip_button.callback = skip_button_callback

        lyrics_button = Button(label="Lyrics", style=discord.ButtonStyle.blurple)
        lyrics_button.callback = lyrics_button_callback

        # Send the embed with buttons
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

    input_type = identify_link_type(search)

    if input_type == 'spotify':
        await handle_spotify_link(ctx, search, vc)
    elif input_type == 'soundcloud':
        await handle_soundcloud_link(ctx, search, vc)
    elif input_type == 'apple_music':
        await handle_apple_music_link(ctx, search, vc)
    elif input_type == 'youtube':
        await handle_youtube_link(ctx, search, vc)
    else:
        await handle_search_query(ctx, search, vc)

            
def identify_link_type(input_str):
    if re.match(r'https?://open\.spotify\.com/', input_str):
        return 'spotify'
    elif re.match(r'https?://(www\.)?soundcloud\.com/', input_str):
        return 'soundcloud'
    elif re.match(r'https?://music\.apple\.com/', input_str):
        return 'apple_music'
    elif re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', input_str):
        return 'youtube'
    else:
        return 'search'

async def handle_spotify_link(ctx, link: str, vc):
    # Extract the type of Spotify link (track, album, playlist)
    if "track" in link:
        track_id = link.split("/")[-1].split("?")[0]
        track = spotify.track(track_id)
        await enqueue_track(ctx, track, vc)
        await ctx.send(f"Added track **{track['name']}** to the queue.")
    elif "album" in link:
        album_id = link.split("/")[-1].split("?")[0]
        results = spotify.album_tracks(album_id)
        tracks = results['items']
        await enqueue_tracks(ctx, tracks, vc)
        await ctx.send(f"Added album **{spotify.album(album_id)['name']}** to the queue.")
    elif "playlist" in link:
        playlist_id = link.split("/")[-1].split("?")[0]
        results = spotify.playlist_tracks(playlist_id)
        tracks = [item['track'] for item in results['items']]
        await enqueue_tracks(ctx, tracks, vc)
        await ctx.send(f"Added playlist **{spotify.playlist(playlist_id)['name']}** to the queue.")
    else:
        await ctx.send("Unsupported Spotify link.")

async def handle_soundcloud_link(ctx, link: str, vc):
    ydl_opts = {
        'format': 'bestaudio/best',
        'ignoreerrors': True,
        'quiet': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        if 'entries' in info:
            entries = info['entries']
        else:
            entries = [info]

        for entry in entries:
            sources = await YTDLSource.create_source(entry['webpage_url'], loop=bot.loop)
            for source in sources:
                await song_queue.put(source)
                if not vc.is_playing() and not vc.is_paused():
                    await play_next(ctx, vc)
    await ctx.send("Added SoundCloud content to the queue.")

async def handle_apple_music_link(ctx, link: str, vc):
    await ctx.send("Attempting to find the song on YouTube...")

    # Extract song title and artist from the link using regex
    match = re.search(r'music\.apple\.com/.+?/(.+?)/(.+)', link)
    if match:
        artist = match.group(1).replace('-', ' ')
        song = match.group(2).split('?')[0].replace('-', ' ')
        search_query = f"{song} {artist}"
    else:
        search_query = link  # Use the link itself as the search query

    await handle_search_query(ctx, search_query, vc)
    
async def handle_youtube_link(ctx, link: str, vc):
    sources = await YTDLSource.create_source(link, loop=bot.loop)
    for source in sources:
        await song_queue.put(source)
        if not vc.is_playing() and not vc.is_paused():
            await play_next(ctx, vc)
    await ctx.send("Added YouTube content to the queue.")


async def handle_search_query(ctx, query: str, vc):
    sources = await YTDLSource.create_source(query, loop=bot.loop)
    for source in sources:
        await song_queue.put(source)
        if not vc.is_playing() and not vc.is_paused():
            await play_next(ctx, vc)
    await ctx.send(f"Added '{query}' to the queue.")

async def enqueue_track(ctx, track, vc):
    track_name = track['name']
    artists = ', '.join([artist['name'] for artist in track['artists']])
    search_query = f"{track_name} {artists}"

    sources = await YTDLSource.create_source(search_query, loop=bot.loop)
    for source in sources:
        await song_queue.put(source)
        if not vc.is_playing() and not vc.is_paused():
            await play_next(ctx, vc)

async def enqueue_tracks(ctx, tracks, vc):
    for track in tracks:
        await enqueue_track(ctx, track, vc)


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



bot.run(BOT_TOKEN)
