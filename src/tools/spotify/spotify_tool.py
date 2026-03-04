import logging
import os
import subprocess
import time
from typing import Dict, List, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
from src.tools.base_tool import BaseTool
from src.tools.device_manager.android_client import AndroidClient
from src.tools.spotify.chromadb_client import ChromaDBClient
from src.tools.spotify.sqlite_client import CacheDB
from datetime import datetime, timezone

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
        load_dotenv()
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(scope="user-modify-playback-state user-read-playback-state")
        )
        self.chromadb_client = ChromaDBClient()
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
        self._device_type = "phone"
        self._device_id = ""
        self._preferred_playlist = "spotify:playlist:2300cDk2Vk3GdKFfEY8ceX"


    def run(self, query: str) -> str:
        """Performs a search on Spotify based on the query"""
        actions, query = self._extract_keywords(query, self._action_keywords)
        self._device_type, query = self._extract_keywords(query, self._device_keywords)
        if self._device_type is None or len(self._device_type) == 0:
            self._device_type = "phone"
        self._wake_up_spotify(self._device_type)
        self._device_id = self._get_device_id()

        self._load_user_playlists_details()
        result_metadata = self._get_data_from_chroma(query, 10)
        self._process_action(actions[0], result_metadata)

        return "llm_input_command"


    def _process_action(self, action: str, chroma_metadata: dict) -> None:
        """Processes the extracted action and performs the corresponding action on Spotify"""
        match action:
            case "resume":
                pass
            case "next":
                pass
            case "prev":
                pass
            case "play":
                self._start_playback(chroma_metadata)
            case "stop":
                pass
            case _:
                logger.error(f"Action {action} not supported")


    def _start_playback(self, chroma_metadata: dict) -> None:
        """Starts playback on Spotify using the given metadata"""
        if chroma_metadata["type"] == "track":
            playlist_uri = f"spotify:playlist:{chroma_metadata["playlist_id"]}"
            self.sp.start_playback(
                device_id=self._device_id,
                context_uri=playlist_uri,
                offset= {
                    "uri": chroma_metadata["uri"]
                }
            )
        else:
            self.sp.start_playback(device_id=self._device_id, context_uri=chroma_metadata["uri"])


    def _get_data_from_chroma(self, query: str, limit: int) -> dict:
        """Retrieves data from ChromaDB based on the given query"""
        result = self.chromadb_client.query_music(query, limit)
        result_tracks_count, result_playlists_count = 0, 0
        tracks_metadata = []
        for item in result["metadatas"][0]:
            if item["type"] == "track":
                result_tracks_count += 1
                tracks_metadata.append(item)
            else:
                result_playlists_count += 1
        data_type = "track" if result_tracks_count >= result_playlists_count else "playlist" # for now the majority of types win

        if data_type == "track":
            return self._get_top_chroma_track(tracks_metadata)
        else:
            return result["metadatas"][0][0]



    def _get_top_chroma_track(self, metadatas: list[dict]) -> dict:
        all_playlists_ids = [meta["playlist_id"] for meta in metadatas]
        with (CacheDB() as db):
            sorted_playlists_ids = db.get_playlists_last_modified(all_playlists_ids)
            sorted_playlists_ids.sort(
                key=lambda x: x[1], reverse=True
            )
        top_playlist_id = sorted_playlists_ids[0][0]
        return metadatas[all_playlists_ids.index(top_playlist_id)]


    def _extract_keywords(self, query: str, keyword_map: dict[str, list[str]]) -> tuple[list[str], str]:
        """
        Extracts keywords from the given query and matches them to entities in the keyword_map dictionary
        :param query -- the query to extract keywords from
        :param keyword_map -- dictionary mapping keywords to entities
        :return: a tuple containing the extracted entities and the remaining query
        """
        found_entities = []
        output_query = query.strip().lower()

        for entity, keywords in keyword_map.items():
            for keyword in keywords:
                pattern = rf"\b{re.escape(keyword.lower())}\b"
                if re.search(pattern, output_query):
                    found_entities.append(entity)
                    output_query = re.sub(pattern, "", output_query).strip()
                    output_query = re.sub(r"\s+", " ", output_query)

        return found_entities, output_query.strip()


    def _get_playlist_tracks_uris(self, playlist_id: str) -> List[str]:
        """
        Retrieves the URIs of all the tracks in the given playlist
        :param playlist_id -- the ID of the playlist to retrieve tracks from
        :return: a list of URIs of all the tracks in the playlist
        """
        logger.info(f"Fetching tracks from playlist {playlist_id}")
        tracks = [ item["track"]["uri"] for item in self.sp.playlist_items(playlist_id=playlist_id, fields="items.track.uri")["items"] ]
        logger.info("Done")
        return tracks


    def _load_user_playlists_details(self) -> None:
        """
        Retrieves the details(uri and name) of all the playlists owned by the current user and saves them in the cache database
        :return: None
        """
        logger.info("Checking cache for playlists...")
        with CacheDB() as db:
            cached_playlists = db.get_playlists_ids_and_snapshot_ids()
        cached_playlist_ids = [ playlist_id for playlist_id, _ in cached_playlists ]

        server_playlists_info = self.sp.current_user_playlists()["items"]
        server_playlists = [ (playlist["id"], playlist["snapshot_id"]) for playlist in server_playlists_info ]

        for playlist_id, snapshot_id in server_playlists:
            if playlist_id not in cached_playlist_ids:
                logger.info(f"Adding playlist {playlist_id} to cache")
                self._handle_uncached_playlist(playlist_id, snapshot_id)
            elif (playlist_id, snapshot_id) not in cached_playlists:
                logger.info(f"Playlist {playlist_id} has changed, updating cache")
                self._handle_snapshot_id_change(playlist_id, snapshot_id)
            else:
                logger.info(f"Playlist {playlist_id} already in cache and up to date")

        logger.info("Done")


    def _handle_uncached_playlist(self, playlist_id: str, snapshot_id: str) -> None:
        """
        Adds a new playlist to the cache database
        :param playlist_id -- the ID of the playlist to add
        :param snapshot_id -- the snapshot ID of the playlist
        :return: None
        """
        playlist_details = self.sp.playlist(playlist_id=playlist_id, fields="uri,name")
        playlist_items = self.sp.playlist_items(playlist_id=playlist_id, fields="items.track(id,uri,name,popularity,artists(id,name)),next,items.added_at")
        tracks_insert_params = []
        chroma_insert_params = []
        latest_track_added_at = datetime.min.replace(tzinfo=timezone.utc)

        with CacheDB() as db:
            db.insert_playlist_details(playlist_id, playlist_details["uri"], playlist_details["name"], snapshot_id)
            self.chromadb_client.add_data([{
                "id": playlist_id,
                "type": "playlist",
                "name": playlist_details["name"],
                "uri": playlist_details["uri"],
                "artist": "Unknown",
                "playlist_id": "Unknown"
            }])

            while True:
                for item in playlist_items["items"]:
                    track_info = item["track"]["id"], item["track"]["uri"], item["track"]["name"], item["track"]["popularity"]
                    artist_info = item["track"]["artists"][0]["id"], item["track"]["artists"][0]["name"]
                    chroma_insert_params.append({
                        "id": track_info[0],
                        "type": "track",
                        "name": track_info[2],
                        "uri": track_info[1],
                        "artist": artist_info[1],
                        "playlist_id": playlist_id
                    })

                    tracks_insert_params.append((track_info + artist_info))
                    latest_track_added_at = max(latest_track_added_at, datetime.fromisoformat(item["added_at"]))
                if not playlist_items["next"]:
                    break
                playlist_items = self.sp.next(playlist_items)

            db.insert_uncached_tracks(playlist_id, tracks_insert_params)
            self.chromadb_client.add_data(chroma_insert_params)
            db.update_playlist_last_modified(playlist_id, latest_track_added_at)


    def _handle_snapshot_id_change(self, playlist_id: str, snapshot_id: str) -> None:
        """
        Updates the cache database if the snapshot ID of the given playlist has changed
        :param playlist_id -- the ID of the playlist to update
        :param snapshot_id -- the new snapshot ID of the playlist
        :return: None
        """
        with CacheDB() as db:
            cached_tracks_ids = set(db.get_tracks_in_playlist(playlist_id))
            server_tracks_ids = set()
            server_playlist_items = self.sp.playlist_items(playlist_id=playlist_id)

            while True:
                for item in server_playlist_items["items"]:
                    server_tracks_ids.add(item["track"]["id"])
                if not server_playlist_items["next"]:
                    break
                server_playlist_items = self.sp.next(server_playlist_items)

            track_intersection = cached_tracks_ids.intersection(server_tracks_ids)
            tracks_to_delete = cached_tracks_ids - track_intersection
            tracks_to_add = server_tracks_ids - track_intersection

            if tracks_to_delete:
                for track in tracks_to_delete:
                    db.delete_track(track, playlist_id)
                    self.chromadb_client.delete_data(ids=[track], where={"playlist_id": playlist_id})
                    logger.info(f"Deleted track {track}")

            if tracks_to_add:
                tracks_insert_params = []
                chroma_insert_params = []
                tracks_to_add = list(tracks_to_add)
                tracks_to_add = [tracks_to_add[i : i + 50] for i in range(0, len(tracks_to_add), 50)]

                for batch in tracks_to_add:
                    tracks_details = self.sp.tracks(batch)["tracks"]
                    for track in tracks_details:
                        tracks_insert_params.append(
                            (
                                track["id"],
                                track["uri"],
                                track["name"],
                                track["popularity"],
                                track["artists"][0]["id"], track["artists"][0]["name"],
                            )
                        )
                        chroma_insert_params.append({
                            "id": track["id"],
                            "type": "track",
                            "playlist_id": playlist_id,
                            "name": track["name"],
                            "uri": track["uri"],
                            "artist": track["artists"][0]["name"]
                        })
                db.insert_uncached_tracks(playlist_id, tracks_insert_params)
                self.chromadb_client.add_data(chroma_insert_params)

            db.update_snapshot_id(playlist_id, snapshot_id)
            db.update_playlist_last_modified(playlist_id, str(datetime.now(tz=timezone.utc)))


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


    def _wake_up_spotify(self, device: str):
        if device == "phone":
            self._wake_up_phone()


    def _wake_up_phone(self):
       with AndroidClient() as adb:
           adb.wake_and_unlock()
           adb.launch_app("com.spotify.music")

       logger.info("Spotify app launched")


    def _get_device_id(self) -> str | None:
        devices = self.sp.devices().get("devices", [])

        for device in devices:
            if device["type"] == self._device_type and device["is_active"]:
                return device["id"]

        return None