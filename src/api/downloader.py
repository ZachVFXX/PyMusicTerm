import io
import logging
from collections.abc import Callable
from pathlib import Path

import music_tag
import yt_dlp
from PIL import Image

from api.lyrics import download_lyrics
from player.util import string_to_seconds

from .ytmusic import SongData

logger: logging.Logger = logging.getLogger(__name__)


def image_to_byte(image: Image.Image) -> bytes:
    # BytesIO is a file-like buffer stored in memory
    img_byte_arr = io.BytesIO()
    # image.save expects a file-like as a argument
    image.save(img_byte_arr, format=image.format)
    # Turn the BytesIO object back into a bytes object
    img_byte_arr_bytes: bytes = img_byte_arr.getvalue()
    return img_byte_arr_bytes


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
            url = f"https://www.youtube.com/watch?v={song.video_id}"
            ydl.download([url])

        # yt-dlp creates the file with .mp3 extension after post-processing
        output_file = Path(download_path) / f"{song.video_id}.mp3"

        if output_file.exists():
            return str(output_file)
        logger.error(f"Downloaded file not found: {output_file}")
        return None

    except Exception:
        logger.exception("Exception when downloading youtube sound.")
        return None


def _delete_file(path: str) -> None:
    Path(path).unlink(missing_ok=True)


class Downloader:
    def __init__(self, download_path: str) -> None:
        self.download_path: str = download_path

    def download(self, song: SongData) -> str | None:
        self.song: SongData = song
        song_path = Path(f"{self.download_path}/{song.video_id}.mp3")

        if song_path.exists():
            return str(song_path)

        # Download and convert in one step with yt-dlp
        converted_path: str | None = _download_from_yt(
            song,
            self.download_path,
            self.on_progress_callback,
        )

        if converted_path is None:
            return None

        # Add metadata tags
        try:
            file_path = music_tag.load_file(converted_path)
            file_path["title"] = song.title
            file_path["artist"] = list(song.artist)
            file_path["artwork"] = image_to_byte(song.thumbnail)
            file_path["album"] = song.album
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

    def on_progress_callback(self, downloaded: int, total: int) -> None:
        """Callback for download progress (compatible with original API)"""
        # This can be extended to match the original Stream-based callback if needed

    def on_progress(self, downloaded: int, total: int) -> None:
        """Legacy method for compatibility"""
        bytes_remaining = total - downloaded
        percent = (downloaded / total) * 100
        logger.info(f"Downloaded {percent:.2f}% of {self.song.title}")
