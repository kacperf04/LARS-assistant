import logging
import sys

import colorlog
import joblib
from dotenv import load_dotenv

from src.tools.spotify.chromadb_client import ChromaDBClient
from src.tools.spotify.spotify_tool import SpotifyTool

classifier = joblib.load('./classifier/pkl/multinomial_naive_bayes.pkl')
vectorizer = joblib.load('./classifier/pkl/vectorizer.pkl')

formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s | [%(levelname)-s] | %(name)s | %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
    log_colors={
        'DEBUG':    'green',
        'INFO':     'cyan',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'red,bg_white',
    }
)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

if __name__ == "__main__":
    load_dotenv()
    chroma_db = ChromaDBClient()

    spClient = SpotifyTool()
    spClient.run("play some blues")
