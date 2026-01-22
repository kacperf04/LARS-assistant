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

        ids = []
        documents = []
        metadatas = []

        for item in data_list:
            ids.append(item["id"])

            if item["type"] == "track":
                doc = f"Track: {item["name"]} by {item["artist"]}"
            else:
                doc = f"Playlist: {item['name']}. A collection of music."

            documents.append(doc)

            metadatas.append({
                "type": item["type"],
                "uri": item["uri"],
                "artist": item.get("artist", "Unknown")
            })

        try:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            print(f"Synched {len(ids)} items to Chroma database.")
        except Exception as e:
            print(f"Error adding data to Chroma database: {e}")


    def query_music(self, query: str, n_results: int = 10) -> list[dict]:
        """Queries the Chroma database for the given query."""
        if not self.collection:
            return []

        results = self.collection.query(query_texts=[query], n_results=n_results)
        return results