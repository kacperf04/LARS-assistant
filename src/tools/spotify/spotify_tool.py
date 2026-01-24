from typing import Dict, List, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
from src.tools.base_tool import BaseTool
from src.tools.spotify.chromadb_client import ChromaDBClient
from src.tools.spotify.sqlite_client import CacheDB


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
        self._device_id = None
        self._preferred_playlist = "spotify:playlist:2300cDk2Vk3GdKFfEY8ceX"


    def run(self, query: str) -> str:
        """Performs a search on Spotify based on the query"""
        actions, query = self._extract_keywords(query, self._action_keywords)
        self._device_id, query = self._extract_keywords(query, self._device_keywords)

        self._load_user_playlists_details()
        result_metadata, llm_input_command = self._get_data_from_chroma(query, 1)
        self._process_action(actions[0], result_metadata)
        print(actions)

        return llm_input_command


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
                print(f"Action {action} not supported")


    def _start_playback(self, chroma_metadata: dict) -> None:
        """Starts playback on Spotify using the given metadata"""
        if chroma_metadata["type"] == "track":
            playlist_uri = f"spotify:playlist:{chroma_metadata["playlist_id"]}"
            self.sp.start_playback(
                device_id=self._device_id,
                context_uri=playlist_uri,
                offset= {
                    "uri": chroma_metadata["track_uri"]
                }
            )


    def _get_data_from_chroma(self, query: str, limit: int) -> tuple[dict, str]:
        """Retrieves data from ChromaDB based on the given query"""
        result = self.chromadb_client.query_music(query, limit)
        result_output, result_metadata = result["documents"][0][0], result["metadatas"][0][0]
        result_type = result_metadata["type"]

        if result_type == "track":
            return {
                "type": "track",
                "track_uri": result_metadata["uri"],
                "playlist_id": result_metadata["playlist_id"]
            }, result_output
        else:
            return {
                "type": "playlist",
                "playlist_uri": result_metadata["uri"]
            }, result_output


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
        print(f"  == Fetching tracks from playlist {playlist_id}... ==")
        tracks = [ item["track"]["uri"] for item in self.sp.playlist_items(playlist_id=playlist_id, fields="items.track.uri")["items"] ]
        print("  Done")
        return tracks


    def _load_user_playlists_details(self) -> None:
        """
        Retrieves the details(uri and name) of all the playlists owned by the current user and saves them in the cache database
        :return: None
        """
        print("== Checking cache for playlists... ==")
        with CacheDB() as db:
            cached_playlists = db.get_playlists_ids_and_snapshot_ids()
        cached_playlist_ids = [ playlist_id for playlist_id, _ in cached_playlists ]

        server_playlists_info = self.sp.current_user_playlists()["items"]
        server_playlists = [ (playlist["id"], playlist["snapshot_id"]) for playlist in server_playlists_info ]

        for playlist_id, snapshot_id in server_playlists:
            if playlist_id not in cached_playlist_ids:
                print(f"  == Adding playlist {playlist_id} to cache... ==")
                self._handle_uncached_playlist(playlist_id, snapshot_id)
            elif (playlist_id, snapshot_id) not in cached_playlists:
                print(f"  == Playlist {playlist_id} has changed, updating cache... ==")
                self._handle_snapshot_id_change(playlist_id, snapshot_id)
            else:
                print(f" == Playlist {playlist_id} already in cache and up to date. ==")

        print("Done")


    def _handle_uncached_playlist(self, playlist_id: str, snapshot_id: str) -> None:
        """
        Adds a new playlist to the cache database
        :param playlist_id -- the ID of the playlist to add
        :param snapshot_id -- the snapshot ID of the playlist
        :return: None
        """
        playlist_details = self.sp.playlist(playlist_id=playlist_id, fields="uri,name")
        playlist_items = self.sp.playlist_items(playlist_id=playlist_id, fields="items.track(id,uri,name,popularity,artists(id,name)),next")
        tracks_insert_params = []
        chroma_insert_params = []

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
                if not playlist_items["next"]:
                    break
                playlist_items = self.sp.next(playlist_items)

            db.insert_uncached_tracks(playlist_id, tracks_insert_params)
            self.chromadb_client.add_data(chroma_insert_params)


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
                    print(f"Deleted track {track}")

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


