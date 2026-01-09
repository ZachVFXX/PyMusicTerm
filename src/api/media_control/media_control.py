import logging
from typing import Type

from api.protocols import PyMusicTermPlayer
from setting import SettingManager

from .media_control_base import MediaControl

logger: logging.Logger = logging.getLogger(__name__)


def get_media_control(
    setting: SettingManager,
    player: PyMusicTermPlayer,
) -> MediaControl:
    if setting.os == "win32":
        from .media_control_win32 import MediaControlWin32

        return MediaControlWin32(player)
    else:
        from .media_control_mpris import MediaControlMPRIS

        return MediaControlMPRIS(player)
