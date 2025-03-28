import datetime
from typing import Iterator, Self

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from src.spotless import SpotlessPlaylist, SpotlessTrackInfo


class _SpotifyPlaylistIterator(Iterator[SpotlessTrackInfo]):
    _sp: spotipy.Spotify
    _playlist_id: str
    _position: int
    _current_tracks: list[dict]

    def __init__(self, sp: spotipy.Spotify, playlist_id: str) -> None:
        self._sp = sp
        self._playlist_id = playlist_id
        self._position = 0
        self._current_tracks = []

    def _construct_track(self, track: dict) -> SpotlessTrackInfo:
        album_image_url = None
        max_album_image_size = 0
        album_images = track["album"]["images"]
        for image in album_images:
            if image["height"] > max_album_image_size:
                max_album_image_size = image["height"]
                album_image_url = image["url"]

        release_date = None
        match track["album"]["release_date_precision"]:
            case "day":
                release_date = datetime.date.fromisoformat(
                    track["album"]["release_date"]
                )
            case "month":
                release_date_parts = track["album"]["release_date"].split("-")

                release_date = datetime.date(
                    int(release_date_parts[0]),
                    int(release_date_parts[1]) + 1,
                    1,
                )
            case "year":
                release_date = datetime.date(
                    int(track["album"]["release_date"]), 1, 1
                )
            case None:
                release_date = None
            case _ as p:
                raise ValueError(f"Unsupported precision «{p}»")

        return SpotlessTrackInfo(
            name=track["name"],
            artists=[artist["name"] for artist in track["artists"]],
            track_number=track["track_number"],
            album_name=track["album"]["name"],
            album_image_url=album_image_url,
            release_date=release_date,
        )

    def __next__(self) -> SpotlessTrackInfo:
        if self._position % 100 == 0:
            tracks = self._sp.playlist_tracks(
                playlist_id=self._playlist_id,
                limit=100,
                offset=100 * (self._position // 100),
            )
            assert tracks is not None

            self._current_tracks = tracks["items"]

        self._position += 1

        if self._position % 100 >= len(self._current_tracks):
            raise StopIteration

        return self._construct_track(
            self._current_tracks[self._position % 100]["track"]
        )

    def __len__(self) -> int:
        return 0


class SpotifyPlaylist(SpotlessPlaylist):
    """
    Allows to get a list of tracks from a Spotify playlist using `spotipy`.
    """

    _sp: spotipy.Spotify
    _playlist_id: str

    def __init__(
        self,
        playlist_id: str,
    ):
        self._sp = spotipy.Spotify(auth_manager=SpotifyOAuth())
        self._playlist_id = playlist_id

        self.name = self._sp.playlist(playlist_id, fields=["name"])["name"]  # type: ignore

    @classmethod
    def from_url(
        cls,
        playlist_url: str,
    ) -> Self:
        return cls(playlist_url.split("/")[-1].split("?")[0])

    def fetch_tracks(self) -> list[SpotlessTrackInfo]:
        return list(_SpotifyPlaylistIterator(self._sp, self._playlist_id))
