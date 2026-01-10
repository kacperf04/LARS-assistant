"""Utility functions for caching Spotify data in SQLite."""

import sqlite3
from typing import Tuple, List


def connect_to_cache_db(db_path: str = "./tools/spotify/.cache/spotify.db") -> Tuple[sqlite3.Connection, sqlite3.Cursor] | Tuple[None, None]:
    """Connects to an SQLite database and returns a connection object and a cursor to it."""
    try:
        print("Connecting to cache database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Connected to database: {db_path}")
        return conn, cursor
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None, None


def create_cache_tables(cursor: sqlite3.Cursor) -> None:
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
    """
    playlist_tracks_table_query = """
        CREATE TABLE IF NOT EXISTS playlist_tracks (
            playlist_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            PRIMARY KEY (playlist_id, track_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id),
            FOREIGN KEY (track_id) REFERENCES tracks(track_id)
        );
    """

    cursor.execute(playlist_table_query)
    cursor.execute(artists_table_query)
    cursor.execute(tracks_table_query)
    cursor.execute(playlist_tracks_table_query)


def check_cache_for_playlist(cursor: sqlite3.Cursor, playlist_id: str) -> bool:
    """Checks if a playlist with the given ID exists in the cache database."""
    return cursor.execute(f"SELECT playlist_id FROM playlists WHERE playlist_id = '{playlist_id}'").fetchone() is not None


def check_playlist_for_snapshot_id_change(cursor: sqlite3.Cursor, playlist_id: str, snapshot_id: str) -> bool:
    """Checks if the snapshot ID of the playlist with the given ID has changed."""
    return cursor.execute(f"SELECT snapshot_id FROM playlists WHERE playlist_id = '{playlist_id}'").fetchone()[0] != snapshot_id


def get_tracks_ids(connection: sqlite3.Connection, cursor: sqlite3.Cursor) -> List[str]:
    """Retrieves the IDs of all the tracks in the cache database."""
    ids = [ row[0] for row in cursor.execute("SELECT track_id FROM tracks").fetchall() ]
    return ids


def get_tracks_in_playlist(connection: sqlite3.Connection, cursor: sqlite3.Cursor, playlist_id: str) -> List[str]:
    """Retrieves the IDs of all the tracks in the given playlist."""
    ids = [ row[0] for row in cursor.execute("SELECT track_id FROM playlist_tracks").fetchall() ]
    return ids


def insert_playlist_details(connection: sqlite3.Connection, cursor: sqlite3.Cursor, playlist_id: str, playlist_uri: str, playlist_name: str, snapshot_id: str) -> None:
    """Inserts the details of a playlist into the cache database."""
    playlist_name = playlist_name.replace("'", "''")
    cursor.execute(f"INSERT INTO playlists VALUES ('{playlist_id}', '{playlist_uri}', '{playlist_name}', '{snapshot_id}')")
    connection.commit()


def insert_track_details(connection: sqlite3.Connection, cursor: sqlite3.Cursor, track_id: str, track_uri: str, track_name: str, track_popularity: float, artist_id: str, artist_name: str) -> None:
    """Inserts the details of a track into the cache database."""
    track_name = track_name.replace("'", "''")
    is_artist_in_db = cursor.execute(f"SELECT artist_id FROM artists WHERE artist_id = '{artist_id}'").fetchone() is not None
    if not is_artist_in_db:
        insert_artist_details(connection, cursor, artist_id, artist_name)
    all_tracks_ids = get_tracks_ids(connection, cursor)
    if not track_id in all_tracks_ids:
        cursor.execute(f"INSERT INTO tracks VALUES ('{track_id}', '{track_uri}', '{track_name}', {track_popularity}, '{artist_id}')")
    connection.commit()


def insert_artist_details(connection: sqlite3.Connection, cursor: sqlite3.Cursor, artist_id: str, artist_name: str) -> None:
    """Inserts the details of an artist into the cache database."""
    artist_name = artist_name.replace("'", "''")
    cursor.execute(f"INSERT INTO artists VALUES ('{artist_id}', '{artist_name}')")
    connection.commit()


def insert_playlist_track(connection: sqlite3.Connection, cursor: sqlite3.Cursor, playlist_id: str, track_id: str) -> None:
    """Inserts a track into a playlist in the cache database."""
    if not track_id in get_tracks_in_playlist(connection, cursor, playlist_id):
        cursor.execute(f"INSERT INTO playlist_tracks VALUES ('{playlist_id}', '{track_id}')")
    connection.commit()


def truncate_cache_tables(connection: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
    """Truncates all tables in the cache database."""
    cursor.execute("DELETE FROM playlists")
    cursor.execute("DELETE FROM artists")
    cursor.execute("DELETE FROM tracks")
    cursor.execute("DELETE FROM playlist_tracks")
    connection.commit()
