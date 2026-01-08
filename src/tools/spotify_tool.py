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


    def _get_users_playlists(self) -> Dict:
        return self.sp.current_user_playlists()


    def run(self, query: str) -> str:
        """Performs a search on Spotify based on the query"""
        actions, query = self._extract_action_keywords(query)
        device_type, query = self._extract_device_type(query)

        self._get_users_playlists()

        '''
        req =  self.sp.search(q=query, limit=10)
        print([req["tracks"]["items"][i]["popularity"] for i in range(10)])
        print(req["tracks"]["items"][0]["name"])
        #self.sp.start_playback(device_id=self._get_active_device(device_type), uris=[req["tracks"]["items"][0]["uri"]])

        print(f"Performing action(s) {actions} on Spotify using device type {device_type}")
        print(f"Query: {query}")
        '''

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


