import logging
from pathlib import Path
from random import shuffle

import music_tag

from api.downloader import Downloader
from api.music_player import MusicPlayer
from api.protocols import SongData
from api.ytmusic import YTMusic
from player.media_control import MediaControl
from player.util import format_time
from setting import SettingManager, fetch_files_from_folder

logger: logging.Logger = logging.getLogger(__name__)


class PyMusicTermPlayer:
    def __init__(
        self,
        setting: SettingManager,
        media_control: MediaControl,
        downloader: Downloader,
    ) -> None:
        self.media_control: MediaControl = media_control
        self.setting: SettingManager = setting
        self.music_player = MusicPlayer(default_volume=self.setting.volume)
        self.ytm = YTMusic()
        self.downloader: Downloader = downloader
        self.list_of_downloaded_songs: list[SongData] = self.get_downloaded_songs()
        self.dict_of_song_result: dict[str, SongData] = {}
        self.current_song_index = 0
        self.current_song: SongData | None = None
        self.lyrics_data: list[tuple[int, str]] | None = None

    def get_downloaded_songs(self) -> list[SongData]:
        songs: list[str | None] = fetch_files_from_folder(self.setting.music_dir, "mp3")
        list_of_songs: list[SongData] = []
        for song in songs:
            song_metadata = music_tag.load_file(song)
            artist = song_metadata["artist"]
            list_of_songs.append(
                SongData(
                    title=str(song_metadata["title"]),
                    artist=artist.values,
                    duration=format_time(float(str(song_metadata["#length"]))),
                    video_id=Path(song).stem,
                    thumbnail=song_metadata["artwork"].first.thumbnail([128, 128]),
                    album=str(song_metadata["album"]),
                    path=Path(song),
                ),
            )
        return list_of_songs

    def query(self, query: str, filter: str) -> list[SongData]:  # noqa: A002
        result: list[SongData] = self.ytm.search(query, filter)

        self.dict_of_song_result.clear()
        for song in result:
            self.dict_of_song_result[song.video_id] = song
        return result

    def play_from_ytb(self, video_id: str) -> None:
        """
        Play a song from the YTMusic API, it will download the song first then play it.
        """
        song: SongData = self.dict_of_song_result[video_id]
        path: str | None = self.downloader.download(song)
        if path is None:
            return
        # BUG: dont re-fetch the songs but add it to the list
        self.list_of_downloaded_songs = self.get_downloaded_songs()
        self.current_song = self.list_of_downloaded_songs[
            len(self.list_of_downloaded_songs) - 1
        ]
        self.current_song_index: int = len(self.list_of_downloaded_songs) - 1
        self.media_control.populate_playlist()
        self.music_player.load_song(str(path))
        self.music_player.play_song()
        self.music_player.volume = self.setting.volume
        self.media_control.set_current_song(self.current_song_index)
        self.media_control.on_playback()

    def play_from_list(self, index: int) -> None:
        self.current_song_index: int = index
        self.current_song = self.list_of_downloaded_songs[index]
        self.music_player.load_song(self.list_of_downloaded_songs[index].path)
        self.music_player.play_song()
        self.music_player.volume = self.setting.volume
        self.media_control.set_current_song(self.current_song_index)
        self.media_control.on_playback()

    def previous(self) -> int:
        """Play the previous song."""
        if not self.list_of_downloaded_songs:
            return 0
        if self.current_song_index == 0:
            self.current_song_index = len(self.list_of_downloaded_songs) - 1
        else:
            self.current_song_index -= 1
        self.current_song = self.list_of_downloaded_songs[self.current_song_index]
        self.music_player.load_song(
            self.list_of_downloaded_songs[self.current_song_index].path,
        )
        self.music_player.play_song()
        self.media_control.set_current_song(self.current_song_index)
        self.media_control.on_playback()
        return self.current_song_index

    def next(self) -> int:
        """Play the next song."""
        if not self.list_of_downloaded_songs:
            return 0
        if self.current_song_index == len(self.list_of_downloaded_songs) - 1:
            self.current_song_index = 0
        else:
            self.current_song_index += 1
        self.current_song = self.list_of_downloaded_songs[self.current_song_index]
        self.music_player.load_song(
            self.list_of_downloaded_songs[self.current_song_index].path,
        )
        self.music_player.play_song()
        self.media_control.set_current_song(self.current_song_index)
        self.media_control.on_playback()
        return self.current_song_index

    def seek(self, seconds: float = 10) -> None:
        """Seek forward or backward."""
        if not isinstance(seconds, int | float):
            msg: str = f"Seconds must be an integer or a float, not {type(seconds)}"
            raise TypeError(msg)
        self.music_player.position += seconds

    def seek_to(self, seconds: float) -> None:
        if not isinstance(seconds, int | float):
            msg: str = f"Seconds must be an integer or a float, not {type(seconds)}"
            raise TypeError(msg)
        self.music_player.position = seconds

    def suffle(self) -> None:
        """Shuffle the list of downloaded songs."""
        shuffle(self.list_of_downloaded_songs)
        if self.current_song is not None:
            self.current_song_index = self.list_of_downloaded_songs.index(
                self.current_song,
            )
        else:
            self.current_song_index = 0
            self.current_song = self.list_of_downloaded_songs[self.current_song_index]
        self.media_control.populate_playlist()
        self.media_control.set_current_song(self.current_song_index)

    def loop_at_end(self) -> bool:
        """Loop at the end."""
        self.music_player.loop_at_end = not self.music_player.loop_at_end
        self.setting.loop = self.music_player.loop_at_end
        return self.music_player.loop_at_end

    def check_if_song_ended(self) -> bool:
        """Check if the song has ended and play the next song or loop it."""
        if self.music_player.loop_at_end:
            return False
        return bool(self.music_player.position == 0 and not self.music_player.playing)

    def delete_song(self, index: int) -> None:
        self.next()
        song: SongData = self.list_of_downloaded_songs[index]
        self.downloader.delete(song)
        self.list_of_downloaded_songs.pop(index)
        logger.info("Deleted song: %s", song)

    def stop(self) -> None:
        self.music_player.unload_song()

    @property
    def song_length(self) -> float:
        """Get the song length."""
        return self.music_player.song_length

    @property
    def position(self) -> float:
        """Get the current position."""
        return self.music_player.position

    def adjust_volume(self, value: float) -> None:
        """Adjust the volume by a given value."""
        self.music_player.volume += value
        self.media_control.on_volume()
        self.setting.volume = self.music_player.volume

    def set_volume(self, value: float) -> None:
        """Set the volume to a specific value."""
        self.music_player.volume = value
        self.media_control.on_volume()
        self.setting.volume = self.music_player.volume

    @property
    def playing(self) -> bool:
        """Get the playing status."""
        return self.music_player.playing

    def pause_song(self) -> None:
        """Pause the song."""
        self.music_player.pause_song()
        self.media_control.on_playpause()

    def resume_song(self) -> None:
        """Resume the song."""
        self.music_player.resume_song()
        self.media_control.on_playpause()
