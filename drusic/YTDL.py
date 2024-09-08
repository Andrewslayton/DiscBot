import asyncio
import yt_dlp as youtube_dl  # Use yt-dlp instead of youtube_dl
import discord
from discord.ext import commands


class YTDLSource(discord.PCMVolumeTransformer):
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'
    }

    ffmpeg_options = {
        'options': '-vn',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    }

    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    def __init__(self, data, *, volume=0.5):
        # Set up FFmpeg audio
        ffmpeg_audio = discord.FFmpegPCMAudio(data['url'], **self.ffmpeg_options)
        super().__init__(ffmpeg_audio, volume)

        # Store data about the song
        self.data = data
        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.duration = data.get('duration')  # Add duration

    @classmethod
    async def create_source(cls, search: str, *, loop=None, volume=0.5):
        loop = loop or asyncio.get_event_loop()

        # Extract information from YouTube (or other sources supported by yt-dlp)
        data = await loop.run_in_executor(None, lambda: cls.ytdl.extract_info(search, download=False))

        # If a playlist, return a list of sources, otherwise return a single source
        if 'entries' in data:
            return [cls(entry, volume=volume) for entry in data['entries']]
        else:
            return [cls(data, volume=volume)]
