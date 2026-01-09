import logging
from pathlib import Path

from PIL import Image
from winrt.windows.foundation import Uri
from winrt.windows.media import (
    MediaPlaybackStatus,
    MediaPlaybackType,
    SystemMediaTransportControls,
    SystemMediaTransportControlsButton,
    SystemMediaTransportControlsButtonPressedEventArgs,
)
from winrt.windows.media.core import MediaSource
from winrt.windows.media.playback import (
    MediaItemDisplayProperties,
    MediaPlaybackItem,
    MediaPlaybackList,
    MediaPlayer,
)
from winrt.windows.storage import StorageFile
from winrt.windows.storage.streams import RandomAccessStreamReference

from api.protocols import PyMusicTermPlayer
from setting import Setting

setting = Setting()

logger: logging.Logger = logging.getLogger(__name__)


class MediaControlWin32:
    def __init__(self) -> None:
        self.player: PyMusicTermPlayer | None = None
        self.media_player: MediaPlayer | None = None
        self.smtc: SystemMediaTransportControls | None = None
        self.playlist: MediaPlaybackList | None = None

    def init(self, player: PyMusicTermPlayer) -> None:
        """Attach SMTC to the PyMusicTermPlayer"""
        self.player = player
        self.media_player = MediaPlayer()
        self.media_player.auto_play = True
        self.populate_playlist()
        self.media_player.volume = 0.0
        # SMTC setup
        self.smtc = self.media_player.system_media_transport_controls
        self.smtc.shuffle_enabled = True
        self.smtc.is_play_enabled = True
        self.smtc.is_pause_enabled = True
        self.smtc.is_next_enabled = len(player.list_of_downloaded_songs) > 1
        self.smtc.is_previous_enabled = len(player.list_of_downloaded_songs) > 1
        self.smtc.is_enabled = True

        def button_pressed(
            _: None,
            args: SystemMediaTransportControlsButtonPressedEventArgs,
        ) -> None:
            logger.info("SMTC button pressed: %s", args.button)
            if args.button == SystemMediaTransportControlsButton.PLAY:
                self.play()
            elif args.button == SystemMediaTransportControlsButton.PAUSE:
                self.pause()
            elif args.button == SystemMediaTransportControlsButton.NEXT:
                self.player.next()
                self.play()
            elif args.button == SystemMediaTransportControlsButton.PREVIOUS:
                self.player.previous()
                self.play()

        self.smtc.add_button_pressed(button_pressed)

    def populate_playlist(self) -> MediaPlaybackList:
        self.playlist = MediaPlaybackList()
        for song in self.player.list_of_downloaded_songs:
            uri: Uri = Uri(f"file:///{song.path.resolve()}")
            source: MediaSource = MediaSource.create_from_uri(uri)
            item: MediaPlaybackItem = MediaPlaybackItem(source)

            # Set ALL metadata directly on the MediaPlaybackItem
            display_props: MediaItemDisplayProperties = item.get_display_properties()
            display_props.type = MediaPlaybackType.MUSIC
            display_props.music_properties.title = song.title or "Unknown Title"
            display_props.music_properties.artist = (
                song.get_formatted_artists() or "Unknown Artist"
            )
            display_props.music_properties.album_title = ""

            display_props.thumbnail = self.get_ras_from_pil(
                song.thumbnail,
                song.video_id,
            )

            item.apply_display_properties(display_props)

            self.playlist.items.append(item)
        self.media_player.source = self.playlist
        return self.playlist

    def get_ras_from_pil(
        self,
        img: Image.Image,
        video_id: str,
    ) -> RandomAccessStreamReference:
        """Convert PIL image to RandomAccessStreamReference for thumbnails"""
        covers_dir = Path(setting.cover_dir)

        tmp_file: Path = covers_dir / f"{video_id}_cover.png"
        img.save(tmp_file, format="PNG")

        storage_file: StorageFile = StorageFile.get_file_from_path_async(
            str(tmp_file.absolute()),
        ).get()
        return RandomAccessStreamReference.create_from_file(storage_file)

    def on_playback(self) -> None:
        pass

    def on_playpause(self) -> None:
        if not self.smtc or not self.player:
            return
        if self.player.playing and self.player.playing:
            self.smtc.playback_status = MediaPlaybackStatus.PLAYING
        else:
            self.smtc.playback_status = MediaPlaybackStatus.PAUSED

    def on_volume(self) -> None:
        pass

    def play(self) -> None:
        if self.player:
            self.player.resume_song()
        self.on_playpause()

    def pause(self) -> None:
        if self.player:
            self.player.pause_song()
        self.on_playpause()

    def set_current_song(self, index: int) -> None:
        if self.playlist and 1 <= index < len(self.playlist.items) + 1:
            self.playlist.move_to(index)
            self.play()
