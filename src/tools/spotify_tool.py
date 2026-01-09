import subprocess
import time
from typing import Dict, List, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
from src.tools.base_tool import BaseTool

class SpotifyTool(BaseTool):
    """
    Implementation of the BaseTool class that handles Spotify queries. Uses spotipy to interact with a user's Spotify account.

    Attributes
    ----------
    sp : spotipy.Spotify
        Object used to interact with Spotify API.
    _action_keywords : Dict[str, List[str]]
        Dictionary mapping actions to perform in Spotify based on keywords extracted from the query.
        They are sorted by decreasing relevance.
    _device_keywords : Dict[str, List[str]]
        Dictionary mapping device types to extract from the query.
    """
    def __init__(self):
        super().__init__("Spotify")
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(scope="user-modify-playback-state user-read-playback-state")
        )
        self._action_keywords = {
            "resume": ["resume", "resume playing", "continue", "unpause", "keep playing"],
            "next": ["next", "skip", "forward", "another one"],
            "prev": ["previous", "back", "last song"],
            "play": ["play", "start", "listen", "put on", "turn on"],
            "stop": ["stop", "pause", "halt", "quiet", "shut up", "freeze"]
        }
        self._device_keywords = {
            "phone": ["phone", "cellphone", "mobile", "smartphone", "iphone", "android"],
            "computer": ["computer", "laptop", "desktop", "pc"]
        }
        self._users_playlists = self._get_user_playlists_details()
        self._preferred_playlist = "spotify:playlist:2300cDk2Vk3GdKFfEY8ceX"


    def _extract_action_keywords(self, query: str) -> Tuple[List[str], str]:
        """Extracts keywords from the given query and matches them to actions to perform in Spotify."""
        actions = []
        output_query = query.strip().lower()

        for action, keywords in self._action_keywords.items():
            for keyword in keywords:
                pattern = rf"\b{re.escape(keyword.lower())}\b"
                if re.search(pattern, output_query):
                    actions.append(action)
                    output_query = re.sub(pattern, "", output_query).strip()
                    output_query = re.sub(r"\s+", " ", output_query)

        return actions, output_query.strip()


    def _extract_device_type(self, query: str) -> Tuple[str, str]:
        """Extracts the device type from the given query."""
        device = ""
        output_query = query.strip().lower()

        for device_type, keywords in self._device_keywords.items():
            for keyword in keywords:
                pattern = rf"\b{re.escape(keyword.lower())}\b"
                if re.search(pattern, query.lower()):
                    device = device_type
                    output_query = re.sub(pattern, "", output_query).strip()
                    output_query = re.sub(r"\s+", " ", output_query)

        return device, output_query.strip()


    def _get_playlist_tracks_uris(self, playlist_id: str) -> List[str]:
        """Retrieves the URIs of all the tracks in the given playlist."""
        print(f"  == Fetching tracks from playlist {playlist_id}... ==")
        tracks = [ item["track"]["uri"] for item in self.sp.playlist_items(playlist_id=playlist_id, fields="items.track.uri")["items"] ]
        print("  Done")
        return tracks


    def _get_user_playlists_details(self) -> Dict[str, Dict[str, str]]:
        """Retrieves the details(uri and name) of all the playlists owned by the current user."""
        print("== Fetching user playlists... ==")
        user_playlists_details = {
            playlist["id"]: {
                "playlist_uri": playlist["uri"],
                "playlist_name": playlist["name"],
                "tracks": self._get_playlist_tracks_uris(playlist["id"])
            }
            for playlist in self.sp.current_user_playlists()["items"]
        }
        print("Done")
        return user_playlists_details


    def _get_top_search_results(self, query: str, limit: int, search_type: str = "track") -> List[Dict[str, str | float]]:
        """Retrieves the top search results for the given query."""
        results = [
            {
                "track_uri": track["uri"],
                "track_name": track["name"],
                "track_popularity": track["popularity"],
                "artist_name": track["artists"][0]["name"]
            }
            for track in self.sp.search(q=query, type=search_type, limit=limit)["tracks"]["items"]
        ]
        results.sort(key=lambda x: x["track_popularity"], reverse=True)
        return results


    def _get_track_from_users_playlist(self, songs_uris: List[str]) -> Tuple[str, str] | None:
        """Checks if the given song is present in any of the user's playlists."""
        playlist_uri = None
        for playlist_id, playlist_details in self._users_playlists.items():
            for song_uri in songs_uris:
                if song_uri in playlist_details["tracks"]:
                    if playlist_uri == self._preferred_playlist:
                        print("KURWAAAA")
                        return playlist_details["playlist_uri"], song_uri
                    playlist_uri = playlist_details["playlist_uri"]
        return None


    def run(self, query: str) -> str:
        """Performs a search on Spotify based on the query"""
        actions, query = self._extract_action_keywords(query)
        device_type, query = self._extract_device_type(query)

        top_tracks_from_query = self._get_top_search_results(query, 10)
        top_tracks_uris = [ track["track_uri"] for track in top_tracks_from_query]

        if found_song_and_playlist := self._get_track_from_users_playlist(top_tracks_uris):
            playlist_id, song_uri = found_song_and_playlist
        else:
            playlist_id, song_uri = None, None

        if self._get_active_device(device_type) is None:
            subprocess.run(["flatpak", "run", "com.spotify.Client"])
            time.sleep(2)

        if playlist_id is not None:
            self.sp.start_playback(device_id=self._get_active_device(device_type), context_uri=playlist_id, offset={"uri": song_uri})
        else:
            self.sp.start_playback(device_id=self._get_active_device(device_type), uris=top_tracks_uris)

        return query


    def _get_active_device(self, device_type: str = "smartphone"):
        """Checks if any devices are currently active, if not it wakes up the first device available"""
        devices = self.sp.devices().get("devices", [])

        if not devices:
            return None

        for d in devices:
            if d["is_active"]:
                return d["id"]

        for d in devices:
            if d["type"] == device_type:
                self.sp.transfer_playback(device_id=d["id"], force_play=True)
                return d["id"]

        return devices[0]["id"]


