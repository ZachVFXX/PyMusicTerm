import io
import logging
from collections.abc import Callable
from pathlib import Path

import yt_dlp
from mediafile import MediaFile, ImageType,Image
from api.lyrics import download_lyrics
from player.util import string_to_seconds

from .ytmusic import SongData

logger: logging.Logger = logging.getLogger(__name__)

class ProgressHook:
    """Progress hook for yt-dlp to track download progress"""

    def __init__(
        self,
        song: SongData,
        callback: Callable[[int, int], None] | None = None,
    ):
        self.song = song
        self.callback = callback

    def __call__(self, d: dict) -> None:
        if d["status"] == "downloading":
            if "total_bytes" in d:
                total = d["total_bytes"]
                downloaded = d["downloaded_bytes"]
            elif "total_bytes_estimate" in d:
                total = d["total_bytes_estimate"]
                downloaded = d["downloaded_bytes"]
            else:
                return

            percent = (downloaded / total) * 100
            logger.info(f"Downloaded {percent:.2f}% of {self.song.title}")

            if self.callback:
                self.callback(downloaded, total)

        elif d["status"] == "finished":
            logger.info(f"Download finished for {self.song.title}")


def _download_from_yt(
    song: SongData,
    download_path: str,
    callback: Callable[[int, int], None] | None = None,
) -> str | None:
    """Download audio from YouTube using yt-dlp"""
    try:
        output_template = str(Path(download_path) / f"{song.video_id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
            ],
            "outtmpl": output_template,
            "progress_hooks": [ProgressHook(song, callback)],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            url: str = f"https://www.youtube.com/watch?v={song.video_id}"
            ydl.download([url])

        output_file: Path = Path(download_path) / f"{song.video_id}.mp3"

        if output_file.exists():
            return str(output_file)
        logger.error(f"Downloaded file not found: {output_file}")
        return None

    except Exception:
        logger.exception("Exception when downloading youtube sound.")
        return None


class Downloader:
    def __init__(
        self,
        download_path: str,
        callback: Callable[[int, int], None] | None = None,
    ) -> None:
        self.download_path: str = download_path
        self.on_progress_callback: Callable[[int, int], None] | None = callback

    def download(self, song: SongData) -> str | None:
        self.song: SongData = song
        song_path = Path(f"{self.download_path}/{song.video_id}.mp3")

        if song_path.exists():
            return str(song_path)

        converted_path: str | None = _download_from_yt(
            song,
            self.download_path,
            self.on_progress_callback,
        )

        if converted_path is None:
            return None

        # Add metadata tags
        try:
            file_path = MediaFile(converted_path)
            file_path.title = song.title
            file_path.artists = list(song.artist)
            file_path.images = [Image(data=song.thumbnail, desc="album cover", type=ImageType.front)]
            file_path.album = song.album
            file_path.save()
        except Exception:
            logger.exception("Failed to add metadata tags")

        # Download lyrics
        try:
            download_lyrics(
                video_id=song.video_id,
                track=song.title,
                artist=song.artist[0] if song.artist else "Unknown Artist",
                album=None,
                duration=string_to_seconds(song.duration),
            )
        except Exception:
            logger.exception("Failed to download lyrics")

        return str(converted_path)

    def delete(self, song: SongData) -> None:
        song_path: Path = Path(f"{self.download_path}/{song.video_id}.mp3")
        if song_path.exists():
            song_path.unlink()

        lyric_path: Path = Path(f"{self.download_path}/{song.video_id}.lrc")
        if lyric_path.exists():
            lyric_path.unlink()
