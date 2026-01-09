import asyncio
import contextlib
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import requests_cache
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Rule,
    Select,
    TabbedContent,
    TabPane,
)
from textual.worker import Worker, get_current_worker
from textual_image.widget import Image as WidgetImage

from api.discord_rpc.rich_presence import rich_presence
from api.downloader import Downloader
from api.lyrics import download_lyrics, parse_lyrics
from api.protocols import SongData
from player.player import PyMusicTermPlayer
from player.util import format_time, string_to_seconds
from setting import SettingManager, rename_console

if TYPE_CHECKING:
    from textual.widget import Widget

from api.media_control.media_control import get_media_control


logger: logging.Logger = logging.getLogger(__name__)


class PyMusicTerm(App, inherit_bindings=False):
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("q", "seek_back", "Seek backward"),
        Binding("s", "play", "Play/Pause"),
        Binding(
            "ctrl+c",
            "app.quit",
            description="Quit",
            tooltip="Quit the application.",
            priority=True,
            id="quit",
        ),
        Binding("space", "play", "Play/Pause"),
        Binding("d", "seek_forward", "Seek forward"),
        Binding("r", "shuffle", "Shuffle"),
        Binding("l", "loop", "Loop at the end"),
        Binding("a", "previous", "Previous song"),
        Binding("e", "next", "Next song"),
        Binding("&", "return_on_search_tab", "Go to the search tab"),
        Binding("é", "return_on_playlist_tab", "Go to the playlist tab"),
        Binding('"', "return_on_lyrics_tab", "Go to the lyrics tab"),
        Binding("j", "adjust_volume(-0.01)", "Volume down"),
        Binding("k", "adjust_volume(0.01)", "Volume up"),
        Binding("raise_volume", "adjust_volume(0.1)", "Volume up"),
        Binding("lower_volume", "adjust_volume(-0.1)", "Volume down"),
        Binding("mute_volume", "mute", "Mute"),
        Binding("m", "mute", "Mute"),
        Binding("ctrl+delete", "delete", "Delete the selected song"),
    ]

    def __init__(self, setting: SettingManager) -> None:
        super().__init__(css_path="pymusicterm.tcss", watch_css=True)
        self.setting: SettingManager = setting
        rename_console("PyMusicTerm")

        self.timer: Widget | None = None

        requests_cache.install_cache(
            f"{self.setting.cache_dir}/cache",
            expire_after=timedelta(hours=1),
        )

        self.downloader = Downloader(self.setting.music_dir, self.progress_callback)
        self.player = PyMusicTermPlayer(
            self.setting,
            self.downloader,
        )
        self.media_control = get_media_control(self.setting, self.player)
        self.player.media_control = self.media_control
        self.media_control.init()

    def compose(self) -> ComposeResult:
        with TabbedContent(classes="search_tabs", id="tabbed_content"):
            with TabPane("Search", id="search"):  # noqa: SIM117
                with Vertical():
                    yield Input(placeholder="Search for a song", id="search_input")
                    yield Select(
                        id="search_sort",
                        options=[
                            ("Songs (default: Stream Youtube Music)", "songs"),
                            ("Video (Stream Youtube Video)", "videos"),
                        ],
                        allow_blank=False,
                    )
                    yield ProgressBar(
                        100,
                        id="progress_bar",
                        show_eta=False,
                        show_percentage=False,
                        disabled=True,
                    )
                    yield ListView(id="search_results")
            with TabPane("Playlist", id="playlist"):  # noqa: SIM117
                with Vertical():
                    yield Input(placeholder="Search for a song", id="playlist_input")
                    yield ListView(id="playlist_results")
            with TabPane("Lyrics", id="lyrics"):  # noqa: SIM117
                with Vertical():
                    yield Button("󰑐", id="refetch_lyrics")
                    yield ListView(id="lyrics_viewer")
        yield Rule()
        with Vertical(classes="info_controls"):
            with Center():
                yield Label(
                    "Unknown Title",
                    id="label_current_song_title",
                    markup=False,
                )
            with Center():
                yield Label(
                    "Unknown Artist",
                    id="label_current_song_artist",
                    markup=False,
                )
        with Horizontal(classes="status_controls"):
            yield Label(
                "--:--",
                id="label_current_song_position",
                classes="control_label",
            )
            yield ProgressBar(
                total=100,
                show_eta=False,
                show_percentage=False,
                id="player_status",
            )
            yield Label("--:--", id="label_song_length", classes="control_label")
        with Horizontal(classes="player_controls"):
            yield Button("󰼨", id="previous")
            yield Button("󰐊", id="play_pause")
            yield Button("󰼧", id="next")
        with Horizontal(classes="player_controls"):
            yield Button("󰒟", id="shuffle")
            yield Button("󰛤", id="loop")

    @on(TabbedContent.TabActivated)
    async def action_select_playlist_tab(
        self,
        event: TabbedContent.TabActivated | None,
    ) -> None:
        """
        If the tab is playlist, clear the options and add the songs to the playlist.
        """
        if event is None or event.tab.id.endswith("playlist"):
            await self.redraw_playlist()

    async def redraw_playlist(self) -> None:
        playlist_results: ListView = self.query_one("#playlist_results")
        children_id: list[str] = [
            child.id.removeprefix("id-") for child in playlist_results.children
        ]
        for song in self.player.list_of_downloaded_songs:
            if song.video_id not in children_id:
                await playlist_results.append(await self._create_song_item(song))

    async def update_time(self) -> None:
        """Update the time label of the player, and update the player."""
        button: Button = self.query_one("#play_pause")
        if self.player.playing:
            button.label = "󰏤"
        else:
            button.label = "󰐊"

        playlist_results: ListView = self.query_one("#playlist_results")
        if self.player.playing:
            for i, item in enumerate(playlist_results.children):
                id_: str = item.id.removeprefix("id-")
                if id_ == self.player.current_song.video_id:
                    playlist_results.index = i

        progress_bar: ProgressBar = self.query_one("#player_status")
        label_current_song_position: Label = self.query_one(
            "#label_current_song_position",
        )
        label_song_length: Label = self.query_one("#label_song_length")
        length_float: float = self.player.song_length
        current_float: float = self.player.position
        label_current_song_position.update(format_time(current_float))
        label_song_length.update(format_time(length_float))
        if self.player.playing:
            label_current_song_title: Label = self.query_one(
                "#label_current_song_title",
            )
            label_current_song_artist: Label = self.query_one(
                "#label_current_song_artist",
            )
            label_current_song_title.update(
                self.player.list_of_downloaded_songs[
                    self.player.current_song_index
                ].title,
            )
            label_current_song_artist.update(
                self.player.list_of_downloaded_songs[
                    self.player.current_song_index
                ].get_formatted_artists(),
            )
        try:
            percentage: float = current_float / length_float
        except ZeroDivisionError:
            percentage = 0.01
        progress_bar.update(
            progress=percentage * 100,
        )
        if self.player.check_if_song_ended():
            await self.action_next()

        if self.player.lyrics_data:
            i = 0
            current_index = 0
            listview: ListView = self.query_one("#lyrics_viewer")
            for time, _ in self.player.lyrics_data:
                if time > current_float:
                    current_index: int = i - 1 if i > 1 else 0
                    break
                i += 1

            for idx, item in enumerate(listview.children):
                if idx == current_index:
                    item.add_class("current_lyrics")
                else:
                    item.remove_class("current_lyrics")

    async def action_return_on_search_tab(self) -> None:
        """Set the search tab as the active tab."""
        tab: TabbedContent = self.query_one("#tabbed_content")
        tab.active = "search"

    async def action_return_on_playlist_tab(self) -> None:
        """Set the playlist tab as the active tab."""
        tab: TabbedContent = self.query_one("#tabbed_content")
        tab.active = "playlist"

    async def action_return_on_lyrics_tab(self) -> None:
        """Set the lyrics tab as the active tab."""
        tab: TabbedContent = self.query_one("#tabbed_content")
        tab.active = "lyrics"

    @on(ListView.Selected, "#playlist_results")
    async def select_playlist_result(self, event: ListView.Selected) -> None:
        """Select a song from the playlist results and play it."""
        id_: str = event.item.id.removeprefix("id-")
        await self.play_from_id(id_)
        await self.update_lyrics_view()

    async def play_from_id(self, ids: str) -> None:
        for i, song in enumerate(self.player.list_of_downloaded_songs):
            if song.video_id == ids:
                self.player.play_from_list(i)
                await self.toggle_button()

    @on(ListView.Selected, "#search_results")
    async def select_result(self, event: ListView.Selected) -> None:
        """Select a song from the search results and play it."""
        video_id: str = str(event.item.id).removeprefix("id-")
        search_results: ListView = self.query_one("#search_results")
        search_results.disabled = True
        progress_bar: ProgressBar = self.query_one("#progress_bar")
        progress_bar.visible = True
        self.download_async(video_id)

    def progress_callback(self, downloaded: int, total: int) -> None:
        progress_bar: ProgressBar = self.query_one("#progress_bar")
        progress_bar.update(progress=downloaded / total * 100)

    @work(thread=True, exclusive=True)
    def download_async(self, video_id: str) -> None:
        worker: Worker = get_current_worker()
        self.player.play_from_ytb(video_id)
        if not worker.is_cancelled:
            self.call_from_thread(self.download_and_update)

    async def download_and_update(self) -> None:
        await self.toggle_button()
        await self.update_lyrics_view()
        search_results: ListView = self.query_one("#search_results")
        search_results.disabled = False
        progress_bar: ProgressBar = self.query_one("#progress_bar")
        progress_bar.visible = False

    async def load_lyric(self, listview: ListView, path: Path) -> None:
        await listview.clear()
        with path.open() as f:
            result: list[tuple[int, str]] = parse_lyrics(f.read())
            i = 0
            for _, lyric in result:
                await listview.append(
                    ListItem(Label(lyric, shrink=True), id=f"id-lyrics-{i}"),
                )
                i += 1  # noqa: SIM113
            self.player.lyrics_data = result

    @on(ListView.Selected, "#lyrics_viewer")
    async def select_lyrics_viewer(self, event: ListView.Selected) -> None:
        id_: int = int(event.item.id.removeprefix("id-lyrics-"))
        time, _ = self.player.lyrics_data[id_]
        self.player.seek_to(time)

    async def update_lyrics_view(self) -> None:
        listview: ListView = self.query_one("#lyrics_viewer")
        if not self.player.current_song:
            await listview.clear()
            return
        path: Path = (
            Path(self.setting.lyrics_dir) / f"{self.player.current_song.video_id}.lrc"
        )
        if path.exists():
            await self.load_lyric(listview, path)
        else:
            song: SongData | None = self.player.current_song
            download_lyrics(
                song.video_id,
                track=song.title,
                album=song.album,
                artist=song.artist[0] if song.artist else "Unknown Artist",
                duration=string_to_seconds(song.duration),
            )
            if path.exists():
                await self.load_lyric(listview, path)

    @on(Button.Pressed, "#refetch_lyrics")
    async def action_refetch_lyrics(self) -> None:
        listview: ListView = self.query_one("#lyrics_viewer")
        if not self.player.current_song:
            await listview.clear()
            return
        path: Path = (
            Path(self.setting.lyrics_dir) / f"{self.player.current_song.video_id}.lrc"
        )

        song: SongData | None = self.player.current_song
        download_lyrics(
            song.video_id,
            track=song.title,
            album=song.album,
            artist=song.artist[0] if song.artist else "Unknown Artist",
            duration=string_to_seconds(song.duration),
        )
        if path.exists():
            await self.load_lyric(listview, path)

    @on(Button.Pressed, "#play_pause")
    async def action_play(self) -> None:
        """Play or pause the song."""
        if self.player.playing:
            self.player.pause_song()
        else:
            self.player.resume_song()
        await self.toggle_button()

    async def toggle_button(self) -> None:
        """Toggle the play button label and start the timer if it's not running."""
        button: Button = self.query_one("#play_pause")
        if self.player.playing:
            button.label = "󰏤"
        else:
            button.label = "󰐊"
        if self.timer is None:
            self.timer = self.set_interval(
                0.1,
                self.update_time,
                name="update_time",
            )

    @on(Button.Pressed, "#previous")
    async def action_previous(self) -> None:
        """Play the previous song."""
        await self.toggle_button()
        playlist_results: ListView = self.query_one("#playlist_results")
        playlist_results.index = self.player.previous()
        await self.update_lyrics_view()

    @on(Button.Pressed, "#next")
    async def action_next(self) -> None:
        """Play the next song."""
        await self.toggle_button()
        playlist_results: ListView = self.query_one("#playlist_results")
        playlist_results.index = self.player.next()
        await self.update_lyrics_view()

    @on(Button.Pressed, "#shuffle")
    async def action_shuffle(self) -> None:
        """Shuffle the list of downloaded songs."""
        playlist_results: ListView = self.query_one("#playlist_results")
        await playlist_results.clear()

        self.player.suffle()
        await self.action_select_playlist_tab(None)

    @on(Button.Pressed, "#loop")
    async def action_loop(self) -> None:
        """Toggle the loop button."""
        loop_button: Button = self.query_one("#loop")
        is_looping: bool = self.player.loop_at_end()
        if is_looping:
            loop_button.variant = "success"
        else:
            loop_button.variant = "default"

    @on(Input.Changed, "#playlist_input")
    async def search_playlist(self) -> None:
        """Search asynchronously on YTMusic."""
        playlist_results: ListView = self.query_one("#playlist_results")
        playlist_input: Input = self.query_one("#playlist_input")
        if playlist_input.value == "":
            await self.action_select_playlist_tab(None)
            return
        await playlist_results.clear()
        for song in self.player.list_of_downloaded_songs:
            if (
                playlist_input.value.lower() in song.title.lower()
                or playlist_input.value.lower() in song.get_formatted_artists().lower()
            ):
                playlist_results.append(await self._create_song_item(song))

    @on(Input.Submitted, "#search_input")
    def search(self) -> None:
        """Search for a song on YTMusic and display the results."""
        search_results: ListView = self.query_one("#search_results")
        search_results.clear()
        search_input: Input = self.query_one("#search_input")
        if search_input.value == "":
            return
        search_results.loading = True
        self.search_ytb_thread(search_input.value)

    @work(exclusive=True, thread=True)
    def search_ytb_thread(self, query: str) -> None:
        worker: Worker = get_current_worker()
        filters: Select = self.query_one("#search_sort")
        results: list[SongData] = self.player.query(query, filters.value)
        if not worker.is_cancelled:
            self.call_from_thread(self.update_search_results, results)

    async def update_search_results(self, results: list[SongData]) -> None:
        search_results: ListView = self.query_one("#search_results")
        search_results.clear()
        for result in results:
            search_results.append(await self._create_song_item(result))
        search_results.loading = False

    async def _create_song_item(self, song: SongData) -> ListItem:
        return ListItem(
            Horizontal(
                WidgetImage(song.thumbnail, classes="image"),
                Vertical(
                    Label(
                        song.title,
                        classes="title",
                        markup=False,
                    ),
                    Label(
                        song.get_formatted_artists(),
                        markup=False,
                        classes="artist",
                    ),
                ),
                Label(
                    song.album,
                    markup=False,
                    classes="album",
                ),
                Label(
                    song.duration,
                    markup=False,
                    classes="length",
                ),
            ),
            id=f"id-{song.video_id}",
            classes="song_item",
        )

    async def action_seek_back(self) -> None:
        """Seek backward 10 seconds."""
        self.player.seek(-10)

    async def action_seek_forward(self) -> None:
        """Seek forward 10 seconds."""
        self.player.seek(10)

    async def action_adjust_volume(self, volume: float) -> None:
        """Increase the volume."""
        self.player.adjust_volume(volume)
        self.notify(
            f"Volume changed to {self.player.music_player.volume:.2f}",
            timeout=0.2,
        )

    async def action_mute(self) -> None:
        """Mute the player."""
        if self.player.music_player.volume == 0:
            self.player.set_volume(self.setting.volume)
            self.notify("Unmuted", timeout=0.2)
        else:
            self.player.set_volume(0)
            self.notify("Muted", timeout=0.2)

    async def action_delete(self) -> None:
        """Delete the selected song."""
        if self.player.current_song:
            logger.info("Deleting song at index %s", self.player.current_song_index)
            self.player.delete_song(self.player.current_song_index)
            playlist_results: ListView = self.query_one("#playlist_results")
            await playlist_results.clear()
            await self.redraw_playlist()
            await self.update_lyrics_view()

    def handle_exception(self, error: Exception) -> None:
        """Handle exceptions to prevent them from being displayed in UI."""
        logger: logging.Logger = logging.getLogger(__name__)

        # Log Rich Presence-related errors quietly
        if (
            "rich_presence" in str(error)
            or "Discord" in str(error)
            or "pypresence" in str(error)
        ):
            logger.debug(f"Rich Presence error (suppressed): {error}")
            return

        # Log other important errors, but do not display them in the UI.
        logger.error(f"Application error: {error}")

    async def on_exception(self, error: Exception) -> None:
        self.handle_exception(error)


async def main() -> None:
    setting = SettingManager()
    app = PyMusicTerm(setting)
    try:
        task: asyncio.Task[None] = asyncio.create_task(
            rich_presence(app.player, start=time.time()),
        )
    except Exception as e:
        logger.warning(f"Rich Presence failed: {e}")
    try:
        await app.run_async()
    finally:
        app.media_control.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    asyncio.run(main())
