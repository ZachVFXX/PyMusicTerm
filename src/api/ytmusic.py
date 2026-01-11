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
            ssl_context: ssl.SSLContext = ssl.create_default_context(
                cafile=certifi.where(),
            )

            # Create custom adapter with SSL context
            adapter = requests.adapters.HTTPAdapter()
            session.mount("https://", adapter)

            # Initialize YTMusic with custom session
            self.client = ytmusicapi.YTMusic(
                requests_session=session,
            )

            logger.info("YTMusic initialized with custom SSL session")
        except Exception as e:
            logger.warning(
                f"Failed to create custom SSL session: {e}, falling back to default",
            )
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

        results: list[dict] = self.client.search(query, filter)

        r: list[SongData] = []
        for result in results:
            title: str = result.get("title", "Unknown Title")
            artist: list[str] = [artist["name"] for artist in result.get("artists", [])]
            if not artist:
                artist = ["Unknown Artist"]
            duration: str = result.get("duration", "Unknown Duration")
            video_id: str = result.get(
                "videoId",
                "dQw4w9WgXcQ",
            )  # Default to a dummy video id
            thumbnail: ImageFile = Image.open(
                requests.get(result["thumbnails"][0]["url"], stream=True).raw,  # noqa: S113
            )
            x = result.get("album", None)
            album = x.get("name") if x else "Unknown Album"
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
