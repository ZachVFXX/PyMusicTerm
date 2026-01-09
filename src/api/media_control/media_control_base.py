from abc import ABC, abstractmethod
from typing import Protocol

from api.protocols import PyMusicTermPlayer


class MediaControl(ABC):
    """
    Abstract base class for media control.
    """

    def __init__(self, player: PyMusicTermPlayer) -> None:
        self.player = player

    @abstractmethod
    def init(self) -> None:
        """
        Initialize the media control.
        """
        ...

    @abstractmethod
    def on_playback(self) -> None:
        """
        Called when playback state changes.
        """
        ...

    @abstractmethod
    def on_playpause(self) -> None:
        """
        Called when play/pause state changes.
        """
        ...

    @abstractmethod
    def on_volume(self) -> None:
        """
        Called when volume changes.
        """
        ...

    @abstractmethod
    def populate_playlist(self) -> None:
        """
        Populate the playlist.
        """
        ...

    @abstractmethod
    def set_current_song(self, index: int) -> None:
        """
        Set the current song.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the media control.
        """
        ...
