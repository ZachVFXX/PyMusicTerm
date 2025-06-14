import io
from collections.abc import Callable
from pathlib import Path

import music_tag
from PIL import Image
from pydub import AudioSegment
from pytubefix import Stream, YouTube

from .ytmusic import SongData


def image_to_byte(image: Image) -> bytes:
    # BytesIO is a file-like buffer stored in memory
    img_byte_arr = io.BytesIO()
    # image.save expects a file-like as a argument
    image.save(img_byte_arr, format=image.format)
    # Turn the BytesIO object back into a bytes object
    img_byte_arr: bytes = img_byte_arr.getvalue()
    return img_byte_arr


def _download_from_yt(
    song: SongData,
    download_path: str,
    callback: None | Callable[[Stream, bytes, int], None] = None,
) -> str | None:
    """
    Download a song from a song.

    Args:
        song (SearchSongResult): The song to download
        download_path (str): The path to download the song to
        callback (None | Callable[[Stream, bytes, int], None]): The callback func use

    Returns:
        path (str): The path of the downloaded file or None if the download failed

    """
    try:
        yt = YouTube(
            f"https://www.youtube.com/watch?v={song.videoId}",
            on_progress_callback=callback,
        )
        return yt.streams.get_audio_only().download(
            output_path=download_path,
            filename=f"{song.videoId}.m4a",
        )
    except Exception as e:
        print(e)
        return None


def _convert_to_mp3(path: str) -> str:
    """
    Convert an audio file to mp3.

    Args:
        path (str): path to the downloanded AUDIO file

    Returns:
        str: path to the mp3 file

    """
    if not isinstance(path, str):
        msg: str = f"path must be a string, not {type(path)}"
        raise TypeError(msg)
    extention: str = Path(path).suffix
    new_path: str = path.replace(extention, ".mp3")
    audio = AudioSegment.from_file(path)
    audio.export(new_path, format="mp3")
    return new_path


def _delete_file(path: str) -> None:
    """
    Delete a file.

    Args:
        path (str): path to the file

    """
    Path(path).unlink(missing_ok=True)


class Downloader:
    def __init__(self, download_path: str) -> None:
        self.download_path: str = download_path

    def download(self, song: SongData) -> str | None:
        """
        Download a song from a song object and return the path of the downloaded file.

        If the file already exists, it will not be downloaded again and the path will be returned.

        Args:
            song (Song): The song to download

        Returns:
            path (str): The path of the downloaded file or None if the download failed

        """
        self.song: SongData = song

        song_path = Path(f"{self.download_path}/{song.videoId}.mp3")
        if song_path.exists():
            return str(song_path)

        yt_path: str | None = _download_from_yt(
            song,
            self.download_path,
            self.on_progress,
        )

        if yt_path is None:
            return None

        converted_path: str = _convert_to_mp3(yt_path)

        file_path = music_tag.load_file(converted_path)
        file_path["title"] = song.title
        file_path["artist"] = [artist for artist in song.artist]
        file_path["artwork"] = image_to_byte(song.thumbnail)
        file_path["album"] = song.album
        file_path.save()

        _delete_file(yt_path)

        return str(converted_path)

    def on_progress(self, stream: Stream, chunk: bytes, bytes_remaining: int) -> None:
        filesize: int = stream.filesize
        bytes_received: int = filesize - bytes_remaining
        percent: float = (bytes_received / filesize) * 100
        print(f"Downloaded {percent:.2f}% of {stream.title}")
