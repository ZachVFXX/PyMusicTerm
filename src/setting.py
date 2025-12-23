import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from msgspec import toml

from log.logger import setup_logging

logger: logging.Logger = logging.getLogger(__name__)

HOME: Path = Path.home()
APP_DIR = Path(HOME / ".pymusicterm")
MUSIC_DIR = Path(APP_DIR / "musics")
SETTING_FILE = Path(APP_DIR / "setting.toml")
PLAYLIST_DIR = Path(APP_DIR / "playlists")
LYRICS_DIR = Path(APP_DIR / "lyrics")
LOG_DIR = Path(APP_DIR / "logs")
CACHE_DIR = Path(APP_DIR / "cache")
COVER_DIR = Path(APP_DIR / "covers")


def is_android() -> bool:
    """Check if running on Android/Termux"""
    # Method 1: Check for Termux-specific environment variable
    if os.environ.get("ANDROID_ROOT"):
        return True

    # Method 2: Check for Android system properties
    if os.path.exists("/system/build.prop"):
        return True

    # Method 3: Check sys.platform and additional Android indicators
    if sys.platform == "linux":
        try:
            # Check if running in Termux
            if "com.termux" in os.environ.get("PREFIX", ""):
                return True
            # Check for Android-specific paths
            if os.path.exists("/data/data/com.termux"):  # noqa: PTH110
                return True
        except:
            pass

    return False


def fetch_files_from_folder(folder_path: str, ending: str = "mp3") -> list[str | None]:
    """
    Fetch all the files from a folder.

    Args:
        folder_path (str): The path of the folder
        ending (str): The ending of the files to fetch. Defaults to "mp3"
    Returns:
        list[str]: The list of file found

    """
    if not isinstance(folder_path, str):
        msg: str = f"folder_path must be a string, not {type(folder_path)}"
        raise TypeError(msg)
    if not isinstance(ending, str):
        msg: str = f"ending must be a string, not {type(ending)}"
        raise TypeError(msg)
    return [str(file) for file in Path(folder_path).glob(f"*.{ending}")]


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    base_path: Path | str = getattr(
        sys,
        "_MEIPASS",
        Path.parent(Path.resolve(__file__)),
    )
    return Path(base_path, relative_path).resolve()


def get_platform():
    if is_android():
        return "android"
    return sys.platform


@dataclass
class Setting:
    """All the settings of the app."""

    volume: float = 1.0
    loop: bool = False
    os: str = get_platform()
    app_dir: str = str(APP_DIR)
    music_dir: str = str(MUSIC_DIR)
    setting_file: str = str(SETTING_FILE)
    playlist_dir: str = str(PLAYLIST_DIR)
    lyrics_dir: str = str(LYRICS_DIR)
    log_dir: str = str(LOG_DIR)
    cache_dir: str = str(CACHE_DIR)
    cover_dir: str = str(COVER_DIR)


class SettingManager:
    """Manages the settings of the app."""

    def __init__(self) -> None:
        self._setting = None
        self.check_and_create_paths()
        self._setting: Setting = self.load_setting()
        setup_logging(self.log_dir)

    @property
    def os(self) -> str:
        return self._setting.os

    @os.setter
    def os(self, value: str) -> None:
        self._setting.os = value
        self.save_setting()

    @property
    def volume(self) -> float:
        return self._setting.volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._setting.volume = round(value, 3)
        self.save_setting()

    @property
    def loop(self) -> bool:
        return self._setting.loop

    @loop.setter
    def loop(self, value: bool) -> None:
        self._setting.loop = value
        self.save_setting()

    @property
    def app_dir(self) -> str:
        return self._setting.app_dir

    @property
    def music_dir(self) -> str:
        return self._setting.music_dir

    @property
    def setting_file(self) -> str:
        return self._setting.setting_file

    @property
    def playlist_dir(self) -> str:
        return self._setting.playlist_dir

    @property
    def lyrics_dir(self) -> str:
        return self._setting.lyrics_dir

    @property
    def log_dir(self) -> str:
        return self._setting.log_dir

    @property
    def cache_dir(self) -> str:
        return self._setting.cache_dir

    @property
    def cover_dir(self) -> str:
        return self._setting.cover_dir

    def load_setting(self) -> Setting:
        """Load settings from the setting.toml file."""
        if not SETTING_FILE.exists():
            self._setting = Setting()
            self.save_setting()

        try:
            with SETTING_FILE.open("rb") as f:
                return toml.decode(f.read(), type=Setting)
        except Exception:
            logger.exception("Error loading settings")
            return Setting()

    def save_setting(self) -> None:
        """Save the current settings to the setting.toml file."""
        try:
            with SETTING_FILE.open("wb") as f:
                encoded: bytes = toml.encode(self._setting)
                f.write(encoded)
        except Exception:
            logger.exception("Error saving settings")

    def check_and_create_paths(self) -> None:
        """Check and create necessary directories and files."""
        APP_DIR.mkdir(exist_ok=True)
        MUSIC_DIR.mkdir(exist_ok=True)
        PLAYLIST_DIR.mkdir(exist_ok=True)
        LYRICS_DIR.mkdir(exist_ok=True)
        LOG_DIR.mkdir(exist_ok=True)
        CACHE_DIR.mkdir(exist_ok=True)
        COVER_DIR.mkdir(exist_ok=True)


@dataclass
class KeyBinding:
    # TODO
    volume_up: str = "k"
    volume_down: str = "j"
    seek_back: str = "q"
    seek_forward: str = "d"
    play_pause: str = "s"


def rename_console(name: str, platform: str = sys.platform) -> None:
    """
    Rename the console.

    Args:
        name (str): The new name of the console (for linux and windows)
        platform (str): The platform of the console (win32 or linux)

    """
    if not isinstance(name, str):
        msg: str = f"name must be a string, not {type(name)}"
        raise TypeError(msg)
    if platform not in ("win32", "linux"):
        msg: str = f"platform must be 'win32' or 'linux', not {platform}"
        raise ValueError(msg)
    if platform == "win32":
        command: str = f"title {name}"
        os.system(command)  # noqa: S605
    if platform in ("linux", "darwin"):
        # Set terminal title for Linux/Unix systems
        # print(f"\033]0;{name}\007", end="", flush=True)
        pass


'''def have_internet() -> bool:
    """Check if the user has internet connection"""
    conn = httplib.HTTPSConnection("8.8.8.8", timeout=5)
    try:
        with conn.request("HEAD", "/"):
            return True
    except Exception:
        return False
'''
