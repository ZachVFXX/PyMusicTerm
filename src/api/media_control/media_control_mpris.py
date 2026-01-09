import logging

from .mpris.mpris import DBusAdapter
from api.protocols import PyMusicTermPlayer
from .media_control_base import MediaControl

logger: logging.Logger = logging.getLogger(__name__)


class MediaControlMPRIS(MediaControl):
    """
    Media control implementation for MPRIS.
    """

    def __init__(self, player: PyMusicTermPlayer) -> None:
        super().__init__(player)
        self.adapter: DBusAdapter = DBusAdapter()
        logger.info("MediaControlMPRIS initialized")

    def init(self) -> None:
        """Initialize with player and start background loop"""
        logger.info("Initializing MediaControlMPRIS with player")
        self.adapter.setup(self.player)
        self.adapter.start_background()

    def on_playback(self) -> None:
        """Handle playback events"""
        return self.adapter.on_playback()

    def on_playpause(self) -> None:
        """Handle play/pause events"""
        return self.adapter.on_playpause()

    def on_volume(self) -> None:
        """Handle volume events"""
        return self.adapter.on_volume()

    def populate_playlist(self) -> None:
        """Populate playlist (no-op for MPRIS)"""

    def set_current_song(self, _: int) -> None:
        """Set current song (no-op for MPRIS)"""

    def stop(self) -> None:
        pass
