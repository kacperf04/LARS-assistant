import joblib
from dotenv import load_dotenv

from src.tools.spotify.chromadb_client import ChromaDBClient
from src.tools.spotify.spotify_tool import SpotifyTool
from src.tools.spotify.sqlite_client import CacheDB

classifier = joblib.load('./classifier/pkl/multinomial_naive_bayes.pkl')
vectorizer = joblib.load('./classifier/pkl/vectorizer.pkl')

if __name__ == "__main__":
    load_dotenv()
    db = ChromaDBClient()
    '''
    db.client.delete_collection("music_library")
    with CacheDB() as db:
        db.truncate_cache_tables()
    '''
    spClient = SpotifyTool()
    spClient.run("play fur elise")
