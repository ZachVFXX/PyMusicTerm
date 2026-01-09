import asyncio
import logging
import threading

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

from api.protocols import PyMusicTermPlayer
from api.ytmusic import SongData

logger: logging.Logger = logging.getLogger(__name__)


class MPRISInterface(ServiceInterface):
    """MPRIS2 Root Interface"""

    def __init__(self, adapter: "DBusAdapter") -> None:
        super().__init__("org.mpris.MediaPlayer2")
        self.adapter: DBusAdapter = adapter

    @method()
    def Raise(self) -> None:
        """Bring the media player to the front"""

    @method()
    def Quit(self) -> None:
        """Quit the media player"""
        import sys

        sys.exit()

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "PyMusicTerm"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return ["file", "http", "https"]

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return ["audio/mpeg", "audio/mp4", "audio/ogg", "audio/flac"]

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> "s":
        return "pymusicterm"

    @dbus_property(access=PropertyAccess.READ)
    def Fullscreen(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanSetFullscreen(self) -> "b":
        return False


class MPRISPlayerInterface(ServiceInterface):
    """MPRIS2 Player Interface"""

    def __init__(self, adapter: "DBusAdapter") -> None:
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.adapter = adapter
        self._rate = 1.0
        self._volume = 1.0
        self._loop_status = "None"
        self._shuffle = False

    @method()
    def Next(self) -> None:
        """Skip to next track"""
        logger.info("MPRIS: Next called")
        if self.adapter.player:
            self.adapter.player.next()
            self.adapter.schedule_update()

    @method()
    def Previous(self) -> None:
        """Skip to previous track"""
        logger.info("MPRIS: Previous called")
        if self.adapter.player:
            self.adapter.player.previous()
            self.adapter.schedule_update()

    @method()
    def Pause(self) -> None:
        """Pause playback"""
        logger.info("MPRIS: Pause called")
        if self.adapter.player:
            self.adapter.player.pause_song()
            self.adapter.schedule_update()

    @method()
    def PlayPause(self) -> None:
        """Toggle play/pause"""
        logger.info("MPRIS: PlayPause called")
        if self.adapter.player:
            if self.adapter.player.playing:
                self.adapter.player.pause_song()
            else:
                self.adapter.player.resume_song()
            self.adapter.schedule_update()

    @method()
    def Stop(self) -> None:
        """Stop playback"""
        logger.info("MPRIS: Stop called")
        if self.adapter.player:
            self.adapter.player.stop()
            self.adapter.schedule_update()

    @method()
    def Play(self) -> None:
        """Start or resume playback"""
        logger.info("MPRIS: Play called")
        if self.adapter.player:
            self.adapter.player.resume_song()
            self.adapter.schedule_update()

    @method()
    def Seek(self, offset: "x") -> None:
        """Seek forward or backward (microseconds)"""
        logger.info(f"MPRIS: Seek called with offset {offset}")
        if self.adapter.player:
            current = self.adapter.player.position
            new_pos = current + (offset / 1000000)
            self.adapter.player.seek_to(max(0, new_pos))

    @method()
    def SetPosition(self, track_id: "o", position: "x") -> None:
        """Set absolute position (microseconds)"""
        logger.info(f"MPRIS: SetPosition called with position {position}")
        if self.adapter.player:
            self.adapter.player.seek_to(position / 1000000)

    @method()
    def OpenUri(self, uri: "s") -> None:
        """Open a URI"""

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        """Current playback status: Playing, Paused, or Stopped"""
        if not self.adapter.player:
            return "Stopped"
        return "Playing" if self.adapter.player.playing else "Paused"

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        """Current track metadata"""
        if (
            not self.adapter.player
            or not self.adapter.player.list_of_downloaded_songs
            or self.adapter.player.current_song_index is None
        ):
            return {}

        try:
            song_data: SongData = self.adapter.player.list_of_downloaded_songs[
                self.adapter.player.current_song_index
            ]

            track_id = f"/org/mpris/MediaPlayer2/Track/{self.adapter.player.current_song_index}"
            length = int(self.adapter.player.song_length * 1000000)

            metadata = {
                "mpris:trackid": Variant("o", track_id),
                "mpris:length": Variant("x", length),
                "mpris:artUrl": Variant(
                    "s",
                    f"https://i.ytimg.com/vi/{song_data.video_id}/maxresdefault.jpg",
                ),
                "xesam:title": Variant("s", song_data.title),
                "xesam:album": Variant("s", song_data.album),
                "xesam:artist": Variant("as", [song_data.get_formatted_artists()]),
                "xesam:url": Variant(
                    "s",
                    f"https://www.youtube.com/watch?v={song_data.video_id}",
                ),
            }

            return metadata
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            return {}

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        """Current position in microseconds"""
        if self.adapter.player:
            return int(self.adapter.player.position * 1000000)
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return True

    @dbus_property()
    def Rate(self) -> "d":
        return self._rate

    @Rate.setter
    def set_rate(self, val: "d") -> None:
        self._rate = val

    @dbus_property()
    def Volume(self) -> "d":
        if self.adapter.player:
            return self.adapter.player.music_player.volume
        return self._volume

    @Volume.setter
    def set_volume(self, val: "d") -> None:
        if self.adapter.player:
            self.adapter.player.set_volume(val)
        self._volume = val
        self.schedule_update()

    @dbus_property()
    def LoopStatus(self) -> "s":
        if self.adapter.player.music_player.loop_at_end:
            return "Track"
        return self._loop_status

    @LoopStatus.setter
    def set_loop_status(self, val: "s") -> None:
        if val == "Track":
            self.adapter.player.music_player.loop_at_end = True
        else:
            self.adapter.player.music_player.loop_at_end = False
        self._loop_status = val
        self.schedule_update()

    @dbus_property()
    def Shuffle(self) -> "b":
        return self._shuffle

    @Shuffle.setter
    def set_shuffle(self, val: "b") -> None:
        self._shuffle = val
        self.schedule_update()


class DBusAdapter:
    """Adapter for dbus-fast MPRIS implementation"""

    def __init__(self) -> None:
        self.player: PyMusicTermPlayer | None = None
        self.bus: MessageBus | None = None
        self.root_interface: MPRISInterface | None = None
        self.player_interface: MPRISPlayerInterface | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = False

    def setup(self, player: PyMusicTermPlayer) -> None:
        """Setup the adapter with a player instance"""
        self.player = player
        logger.info("DBusAdapter setup complete")

    def _run_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Run the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            loop.close()

    async def _start_server(self) -> None:
        """Start the DBus server"""
        try:
            logger.info("Connecting to session bus...")
            self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
            logger.info("Connected to session bus")

            self.root_interface = MPRISInterface(self)
            self.player_interface = MPRISPlayerInterface(self)

            self.bus.export("/org/mpris/MediaPlayer2", self.root_interface)
            self.bus.export("/org/mpris/MediaPlayer2", self.player_interface)
            logger.info("Interfaces exported")

            await self.bus.request_name("org.mpris.MediaPlayer2.PyMusicTerm")
            logger.info("MPRIS DBus server started successfully")

            self._started = True

        except Exception as e:
            logger.error(f"Failed to start DBus server: {e}")
            self._started = False

    def start_background(self) -> None:
        """Start the DBus server in a background thread"""
        if self._thread is not None and self._thread.is_alive():
            logger.info("DBus server already running")
            return

        logger.info("Starting DBus server in background thread...")
        self._loop = asyncio.new_event_loop()

        self._thread = threading.Thread(
            target=self._run_event_loop,
            args=(self._loop,),
            daemon=True,
            name="MPRIS-DBus-Thread",
        )
        self._thread.start()

        # Schedule the server start in the new loop
        asyncio.run_coroutine_threadsafe(self._start_server(), self._loop)

        # Give it a moment to start
        import time

        time.sleep(0.5)

        if self._started:
            logger.info("DBus server thread started successfully")
        else:
            logger.warning("DBus server may not have started correctly")

    def schedule_update(self) -> None:
        """Schedule a property update in the event loop"""
        if self._loop and self.player_interface and self._started:
            future = asyncio.run_coroutine_threadsafe(
                self._emit_properties_changed(),
                self._loop,
            )
            try:
                future.result(timeout=1)  # Wait for a short time
            except Exception as e:
                logger.error(
                    f"Error scheduling properties changed: {e}",
                    exc_info=True,
                )

    async def _emit_properties_changed(self) -> None:
        """Emit properties changed signal for all properties"""
        try:
            if self.player_interface:
                # Emit a signal for each property that might have changed
                props_to_emit = [
                    "PlaybackStatus",
                    "Metadata",
                    "Volume",
                    "Rate",
                    "LoopStatus",
                    "Shuffle",
                ]
                for prop_name in props_to_emit:
                    self.player_interface.emit_properties_changed(
                        {prop_name: getattr(self.player_interface, prop_name)},
                    )
                logger.debug("Properties changed signals emitted for all properties")
        except Exception as e:
            logger.error(f"Error emitting properties changed: {e}", exc_info=True)

    def on_playback(self) -> None:
        """Called when playback state changes"""
        self.schedule_update()

    def on_playpause(self) -> None:
        """Called when play/pause state changes"""
        self.schedule_update()

    def on_volume(self) -> None:
        """Called when volume changes"""
