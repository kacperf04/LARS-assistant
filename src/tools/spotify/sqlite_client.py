"""Utility functions for caching Spotify data in SQLite."""

import sqlite3
from typing import Optional


class CacheDB:
    def __init__(self, db_path: str = "./tools/spotify/.cache/sqlite/spotify.db") -> None:
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None


    def __enter__(self):
        self.connect()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


    def connect(self) -> None:
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.cursor = self.connection.cursor()
            self.cursor.execute("PRAGMA foreign_keys = ON;")
            self._create_tables()
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")


    def close(self) -> None:
        if self.connection:
            self.connection.commit()
            self.connection.close()


    def _create_tables(self) -> None:
        """Creates the required tables in the cache database."""
        playlist_table_query = """
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id TEXT PRIMARY KEY,
                playlist_uri TEXT NOT NULL,
                playlist_name TEXT NOT NULL,
                snapshot_id TEXT NOT NULL
            );
        """
        artists_table_query = """
            CREATE TABLE IF NOT EXISTS artists (
                artist_id TEXT PRIMARY KEY,
                artist_name TEXT NOT NULL
            );
                CREATE UNIQUE INDEX IF NOT EXISTS artist_id_index ON artists (artist_id, artist_name);
        """
        tracks_table_query = """
            CREATE TABLE IF NOT EXISTS tracks (
                track_id TEXT PRIMARY KEY,
                track_uri TEXT NOT NULL,
                track_name TEXT NOT NULL,
                track_popularity REAL NOT NULL,
                artist_id TEXT NOT NULL,
                FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS track_id_index ON tracks (track_id, track_name, track_popularity, artist_id);
        """
        playlist_tracks_table_query = """
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                playlist_id TEXT NOT NULL,
                track_id TEXT NOT NULL,
                PRIMARY KEY (playlist_id, track_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id),
                FOREIGN KEY (track_id) REFERENCES tracks(track_id)
            );
            CREATE INDEX IF NOT EXISTS playlist_tracks_index ON playlist_tracks (playlist_id, track_id);
        """

        self.cursor.executescript(f"""
            BEGIN;
            {playlist_table_query}
            {artists_table_query}
            {tracks_table_query}
            {playlist_tracks_table_query}
            COMMIT;
        """)


    def check_cache_for_playlist(self, playlist_id: str) -> bool:
        """Checks if a playlist with the given ID exists in the cache database."""
        query = "SELECT playlist_id FROM playlists WHERE playlist_id = ?"
        return self.cursor.execute(query, (playlist_id,)).fetchone() is not None


    def check_playlist_for_snapshot_id_change(self, playlist_id: str, snapshot_id: str) -> bool:
        """Checks if the snapshot ID of the playlist with the given ID has changed."""
        query = "SELECT snapshot_id FROM playlists WHERE playlist_id = ?"
        return self.cursor.execute(query, (playlist_id,)).fetchone()[0] != snapshot_id


    def get_tracks_ids(self) -> list[str]:
        """Retrieves the IDs of all the tracks in the cache database."""
        ids = [row[0] for row in self.cursor.execute("SELECT track_id FROM tracks").fetchall()]
        return ids


    def get_tracks_in_playlist(self, playlist_id: str) -> list[str]:
        """Retrieves the IDs of all the tracks in the given playlist."""
        query = "SELECT track_id FROM playlist_tracks WHERE playlist_id = ?"
        ids = [ row[0] for row in self.cursor.execute(query, (playlist_id,)).fetchall() ]
        return ids


    def get_leftover_tracks_ids(self) -> list[str]:
        """Retrieves the IDs of all the tracks that are not present in any playlist in the cache database."""
        ids = [row[0] for row in
               self.cursor.execute("SELECT t.track_id FROM tracks t LEFT JOIN playlist_tracks pt ON t.track_id = pt.track_id WHERE pt.track_id IS NULL").fetchall()]
        return ids


    def get_leftover_artists_ids(self) -> list[str]:
        """Retrieves the IDs of all the artists that are not assigned to any track in the cache database."""
        ids = [row[0] for row in
               self.cursor.execute("SELECT a.artist_id FROM artists a LEFT JOIN tracks t ON a.artist_id = t.artist_id WHERE t.artist_id IS NULL").fetchall()]
        return ids


    def get_playlists_ids_and_snapshot_ids(self) -> list[str]:
        """Retrieves the ID and snapshot ID of the playlist with the given URI."""
        query = "SELECT playlist_id, snapshot_id FROM playlists"
        return self.cursor.execute(query).fetchall()


    def insert_playlist_details(self, playlist_id: str, playlist_uri: str, playlist_name: str, snapshot_id: str) -> None:
        """Inserts the details of a playlist into the cache database."""
        query = "INSERT INTO playlists VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (playlist_id, playlist_uri, playlist_name, snapshot_id))


    def insert_uncached_tracks(self, playlist_id: str, tracks: list[tuple[str, str, str, float, str, str]]) -> None:
        """Inserts multiple tracks into the cache database."""
        artists_to_insert = []
        tracks_to_insert = []
        tracks_to_insert_ids = []
        for track in tracks:
            track_id, track_uri, track_name, track_popularity, artist_id, artist_name = track

            artists_to_insert.append((artist_id, artist_name))
            tracks_to_insert.append((track_id, track_uri, track_name, track_popularity, artist_id))
            tracks_to_insert_ids.append(track_id)
        self.cursor.executemany("INSERT OR IGNORE INTO artists VALUES (?, ?)", artists_to_insert)
        self.cursor.executemany("INSERT OR IGNORE INTO tracks VALUES (?, ?, ?, ?, ?)", tracks_to_insert)
        self.cursor.executemany("INSERT OR IGNORE INTO playlist_tracks VALUES (?, ?)", [(playlist_id, track_id) for track_id in tracks_to_insert_ids])


    def insert_artist_details(self, artist_id: str, artist_name: str) -> None:
        """Inserts the details of an artist into the cache database."""
        query = "INSERT INTO artists VALUES (?, ?)"
        self.cursor.execute(query, (artist_id, artist_name))


    def insert_playlist_track(self, playlist_id: str, track_id: str) -> None:
        """Inserts a track into a playlist in the cache database."""
        if not track_id in self.get_tracks_in_playlist(playlist_id):
            query = "INSERT INTO playlist_tracks VALUES (?, ?)"
            self.cursor.execute(query, (playlist_id, track_id))


    def update_snapshot_id(self, playlist_id: str, snapshot_id: str) -> None:
        """Updates the snapshot ID of a playlist in the cache database."""
        query = "UPDATE playlists SET snapshot_id = ? WHERE playlist_id = ?"
        self.cursor.execute(query, (snapshot_id, playlist_id))


    def delete_track(self, track_id: str, playlist_id: str) -> None:
        """Deletes a track from the cache database."""
        pt_query = "DELETE FROM playlist_tracks WHERE track_id = ? AND playlist_id = ?"
        self.cursor.execute(pt_query, (track_id, playlist_id))

        tracks_to_delete = self.get_leftover_tracks_ids()
        artists_to_delete = self.get_leftover_artists_ids()
        for track_id in tracks_to_delete:
            t_query = "DELETE FROM tracks WHERE track_id = ?"
            self.cursor.execute(t_query, (track_id, ))
        for artist_id in artists_to_delete:
            a_query = "DELETE FROM artists WHERE artist_id = ?"
            self.cursor.execute(a_query, (artist_id, ))


    def truncate_cache_tables(self) -> None:
        """Truncates all tables in the cache database."""
        self.cursor.execute("DELETE FROM playlist_tracks")
        self.cursor.execute("DELETE FROM tracks")
        self.cursor.execute("DELETE FROM playlists")
        self.cursor.execute("DELETE FROM artists")