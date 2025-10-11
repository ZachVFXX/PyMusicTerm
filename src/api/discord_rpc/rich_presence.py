import asyncio
import contextlib
import logging
import time

from pypresence import ActivityType, AioPresence, DiscordNotFound

from api.protocols import PyMusicTermPlayer, SongData

CLIENT_ID = "1275918029565464608"
UPDATE_INTERVAL = 0.7
NO_SONG_SLEEP_INTERVAL = 5
MAX_RETRIES = 3
RETRY_DELAY = 5

logger: logging.Logger = logging.getLogger(__name__)


class RichPresenceError(Exception):
    """Custom exception for Rich Presence errors."""


def create_progress_bar(percentage: int) -> str:
    """Create a text-based progress bar."""
    percentage = max(0, min(percentage, 100))
    total_segments = 8
    completed_segments: int = round((percentage / 100) * total_segments)
    return "▰" * completed_segments + "▱" * (total_segments - completed_segments)


def format_time(seconds: float) -> str:
    """Format seconds into MM:SS string."""
    return time.strftime("%M:%S", time.gmtime(seconds))


async def rich_presence(player: PyMusicTermPlayer, start: int) -> None:
    """Main function to run the Rich Presence update loop."""
    rpc = None
    retry_count = 0
    
    try:
        rpc = AioPresence(CLIENT_ID)
        await rpc.connect()
        logger.info("Discord Rich Presence connected successfully")

        while True:
            try:
                song: SongData | None = player.current_song
                if song is None:
                    logger.debug("No song is playing")
                    await asyncio.sleep(NO_SONG_SLEEP_INTERVAL)
                    continue
                    
                try:
                    artist_name: str = song.get_formatted_artists()
                    song_name: str = song.title
                    album_name: str = song.album
                    track_length: int = player.music_player.song_length
                    track_time: int = player.music_player.position

                    current_time: str = format_time(track_time)
                    song_length: str = format_time(track_length)
                    try:
                        progress_percentage = int((track_time / track_length) * 100)
                    except ZeroDivisionError:
                        progress_percentage = 0

                    await rpc.update(
                        activity_type=ActivityType.LISTENING,
                        large_text=f"{current_time} {create_progress_bar(progress_percentage)} {song_length}",
                        details=f"{song_name} - {artist_name}",
                        large_image="play" if player.playing else "pause",
                        state=f"Album: {album_name}",
                        start=start,
                    )
                    
                    # if succes reset retry count
                    retry_count = 0

                except KeyError as e:
                    logger.warning(f"Missing key in song data: {e}")
                    await asyncio.sleep(UPDATE_INTERVAL)
                    continue
                except Exception as e:
                    logger.warning(f"Failed to update rich presence: {e}")
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        logger.error("Max retries exceeded for Rich Presence updates")
                        return  # end
                    await asyncio.sleep(RETRY_DELAY)
                    continue

                await asyncio.sleep(UPDATE_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("Rich Presence task cancelled")
                break
            except Exception as e:
                logger.warning(f"Unexpected error in Rich Presence update loop: {e}")
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    logger.error("Too many errors in Rich Presence, stopping")
                    return
                await asyncio.sleep(RETRY_DELAY)
                
    except DiscordNotFound:
        logger.info("Discord not found - Rich Presence disabled")
        return  # end
    except Exception as e:
        logger.warning(f"Rich Presence initialization failed: {e}")
        return  # end
    finally:
        # organize process
        if rpc:
            try:
                await rpc.clear()
                await rpc.close()
                logger.debug("Rich Presence connection closed")
            except Exception as e:
                logger.debug(f"Error closing Rich Presence: {e}")
