from typing import Optional
import chromadb

class ChromaDBClient:
    def __init__(self, db_path: str = "./tools/spotify/.cache/chroma"):
        self.db_path = db_path
        self.client: Optional[chromadb.PersistentClient] = None
        self.connection: Optional[chromadb.Collection] = None

        self.connect()
        self.setup_collection()


    def connect(self) -> None:
        """Connects to the Chroma database."""
        try:
            self.client = chromadb.PersistentClient(self.db_path)
        except Exception as e:
            print(f"Error connecting to Chroma database: {e}")
            raise


    def setup_collection(self) -> None:
        """Creates a collection in the Chroma database if it doesn't exist and returns it."""
        if not self.client:
            return

        try:
            self.collection = self.client.get_or_create_collection(
                name="music_library",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"Error setting up collection: {e}")


    def add_data(self, data_list: list[dict]) -> None:
        """Tries to update data in the Chroma database. If an item doesn't exist, it will be added."""
        if not self.collection:
            return

        batch_ids, batch_docs, batch_metas = [], [], []
        seen_ids = set()

        for item in data_list:
            is_track = item["type"] == "track"
            unique_id = f"{item["playlist_id"]}_{item["id"]}" if is_track else item["id"]
            if unique_id in seen_ids:
                continue
            seen_ids.add(unique_id)
            doc = f"Track: {item['name']} by {item.get('artist', 'Unknown')}" if is_track else f"Playlist: {item['name']}"

            if is_track:
                metadata = {
                    "type": "track",
                    "uri": item["uri"],
                    "artist": item.get("artist", "Unknown"),
                    "playlist_id": item.get("playlist_id", "Unknown")
                }
            else:
                metadata = {
                    "type": "playlist",
                    "uri": item["uri"]
                }

            batch_ids.append(unique_id)
            batch_docs.append(doc)
            batch_metas.append(metadata)

        chunk_size = 100
        for i in range(0, len(batch_ids), chunk_size):
            try:
                self.collection.upsert(
                    ids=batch_ids[i:i+chunk_size],
                    documents=batch_docs[i:i+chunk_size],
                    metadatas=batch_metas[i:i+chunk_size]
                )
            except Exception as e:
                print(f"Error adding data to Chroma as index {i}: {e}")

        print(f"Sync attempted for {len(batch_ids)} items.")


    def delete_data(self, ids: list[str], where: dict[str, str]) -> None:
        """Deletes the given items from the Chroma database."""
        if not self.collection or not ids:
            return

        self.collection.delete(ids=ids, where=where)


    def query_music(self, query: str, n_results: int = 10) -> list[dict]:
        """Queries the Chroma database for the given query."""
        if not self.collection:
            return []

        results = self.collection.query(query_texts=[query], n_results=n_results)
        return results