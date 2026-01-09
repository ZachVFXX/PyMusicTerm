from api.protocols import PyMusicTermPlayer
from .smtc.smtc import MediaControlWin32 as MediaControlWin
from .media_control_base import MediaControl


class MediaControlWin32(MediaControl, MediaControlWin):
    """
    Media control implementation for Windows.
    """

    def __init__(self, player: PyMusicTermPlayer) -> None:
        super().__init__(player)

    def init(self) -> None:
        return super().init(self.player)

    def on_playback(self) -> None:
        return super().on_playback()

    def on_playpause(self) -> None:
        return super().on_playpause()

    def on_volume(self) -> None:
        return super().on_volume()

    def populate_playlist(self) -> None:
        return super().populate_playlist()

    def set_current_song(self, index: int) -> None:
        return super().set_current_song(index)

    def stop(self) -> None:
        pass
