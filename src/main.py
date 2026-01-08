import joblib
from dotenv import load_dotenv

from src.tools.spotify_tool import SpotifyTool

classifier = joblib.load('./classifier/pkl/multinomial_naive_bayes.pkl')
vectorizer = joblib.load('./classifier/pkl/vectorizer.pkl')

if __name__ == "__main__":
    load_dotenv()
    spClient = SpotifyTool()
    spClient.run("aa")
