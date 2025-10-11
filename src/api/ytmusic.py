import logging
import ssl
from dataclasses import dataclass

import certifi
import requests
import ytmusicapi
from PIL import Image
from PIL.ImageFile import ImageFile

from api.protocols import SongData

logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class LyricsResult:
    lyrics: str
    source: str


class YTMusic:
    def __init__(self) -> None:
        # Create a custom session with proper SSL configuration
        try:
            session = requests.Session()
            session.verify = certifi.where()
            
            # Create SSL context explicitly
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            # Create custom adapter with SSL context
            adapter = requests.adapters.HTTPAdapter()
            session.mount('https://', adapter)
            
            # Initialize YTMusic with custom session
            self.client = ytmusicapi.YTMusic()
            self.client._session = session
            
            logger.info("YTMusic initialized with custom SSL session")
        except Exception as e:
            logger.warning(f"Failed to create custom SSL session: {e}, falling back to default")
            self.client = ytmusicapi.YTMusic()

    def search(self, query: str, filter: str = "songs") -> list[SongData]:  # noqa: A002
        """
        Search for a song on YTMusic.

        Args:
            query (str): The query to search for
            filter (str, optional): The filter to use. Defaults to "songs".

        Raises:
            TypeError: If query or filter is not a string

        Returns:
            list[Song]: The list of songs found

        """
        if not isinstance(query, str):
            msg: str = f"query must be a string, not {type(query)}"
            raise TypeError(msg)
        if not isinstance(filter, str):
            msg = f"filter must be a string, not {type(filter)}"
            raise TypeError(msg)

        # Search without filter to get all types of results
        # Then filter for songs manually due to YouTube Music API limitations on Linux
        try:
            # Try with filter first
            results: list[dict] = self.client.search(query, filter)
            if not results:
                # Fall back to no filter and manual filtering
                logger.info("No results with filter, trying without filter")
                all_results = self.client.search(query)
                # Filter for song-like results
                results = [r for r in all_results if 
                          r.get('resultType') in ['song', 'video'] or 
                          ('videoId' in r and 'title' in r)]
        except Exception as e:
            logger.warning(f"Search failed: {e}, trying without filter")
            try:
                all_results = self.client.search(query)
                results = [r for r in all_results if 
                          r.get('resultType') in ['song', 'video'] or 
                          ('videoId' in r and 'title' in r)]
            except Exception as e2:
                logger.error(f"Both search methods failed: {e2}")
                results = []

        r: list[SongData] = []
        for result in results:
            title: str = result.get("title", "Unknown")
            artists_data = result.get("artists", [])
            artist: list[str] = [artist["name"] for artist in artists_data if isinstance(artist, dict) and "name" in artist]
            
            if not artist:
                artist = ["Unknown Artist"]
            duration: str = result.get("duration", "Unknown")
            video_id: str = result.get("videoId", "Unknown")
            
            # Handle thumbnail
            try:
                thumbnail: ImageFile = Image.open(
                    requests.get(result["thumbnails"][0]["url"], stream=True).raw,  # noqa: S113
                )
            except (KeyError, IndexError, Exception):
                # Create a placeholder if thumbnail fails
                thumbnail = None
                
            x = result.get("album", None)
            album = x.get("name") if x else "Unknown"
            r.append(
                SongData(
                    title=title,
                    artist=artist,
                    duration=duration,
                    video_id=video_id,
                    thumbnail=thumbnail,
                    album=album,
                ),
            )
        return r
