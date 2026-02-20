# LARS: Low-power Adaptive Routing System
> A modular, locally-hosted AI assistant engineered for edge-computing and optimized to run on low-power devices like the Raspberry Pi.
> 
LARS is designed to execute complex real-world tasks via natural language. Currently, LARS features a highly optimized, custom-built Spotify integration that uses a dual-database caching architecture and physical hardware automation to bypass common API limitations without consuming excessive system resources.

## Key features:

### Custom NLP Intent Classifier
Instead of relying on heavy LLMs for basic routing, LARS uses a lightweight, custom-trained Machine Learning pipeline to classify user commands.
* Built using **Scikit-Learn** (`TfidfVectorizer` + `MultinomialNB`).
* Uses a strictly evaluated K-Fold Cross-Validation pipeline.
* Designed to be later integrated with an LLM for intent routing.

### Dual-Database Smart Caching (Spotify)
In order to not have to rely on API rate limits and ensure fast responses, LARS maintains a local synchronized copy of the user's Spotify library.
* **SQLite (Relational):** Caches playlists, tracks, and artists.
* **ChromaDB (Vector):** Stores track and playlist metadata for semantic/similarity search.
* **Differential Updates:** Tracks Spotify playlist `snapshot_id`. Instead of re-downloading entire playlists, LARS only fetches and updates the exact tracks that were added or removed.

### Physical Hardware Automation (ADB)
A major limitation of the Spotify API is that it cannot start playback unless a device is already active. LARS solves this via hardware automation.
* Uses **Android Debug Bridge (ADB)** to connect to the device, wake the screen, input security PIN and launch the Spotify app to force an active state before executing API playback commands.
* Although not needed, it is recommended to use a connectivity platform (like Tailscale) to avoid problems when switching networks or restarting your phone.

--- 

## Tech Stack

* **Target Hardware:** Raspberry Pi (at least 8GB of RAM)
* **Language:** Python 3.12+
* **ML/Data:** `scikit-learn`, `pandas`
* **Databases:** `SQLite3`, `ChromaDB`
* **APIs & Integration:** `spotipy`, `ADB`

---

## Getting started

### Prerequisites
1. Python 3.12 or higher.
2. A Spotify Developer account.
3. An Android phone with **Wireless Debugging** enabled.
4. ADB on your host machine.
5. Tailscale network with your phone and host machine both connected (not needed but recommended).

### Installation

1. **Clone the repo:**
```bash
git clone [https://github.com/yourusername/LARS-assistant.git](https://github.com/yourusername/LARS-assistant.git)
cd LARS-assistant
```
2. **Install dependencies**
```bash
pip install requirements.txt
```
3. **Environment setup**
Create a `.env` file in the root directory and add the following variables:
```
# Spotify Credentials
SPOTIPY_CLIENT_ID="your_spotify_client_id"
SPOTIPY_CLIENT_SECRET="your_spotify_client_secret"
SPOTIPY_REDIRECT_URI="http://localhost:8080" # Or your configured URI

# ADB Configuration
PHONE_IP="192.168.X.X"
PHONE_DEBUG_PORT="5555"
PHONE_PIN="1234" # Your phone's unlock PIN
```
4. Run the application:
```bash
python -m src.main
```

---

## Project Structure
```
LARS-assistant/
├── src/
│   ├── main.py                     # Entry point
│   ├── classifier/                 # NLP Intent Classification pipeline
│   │   ├── pkl/                    # Serialized joblib models
│   │   └── training_data/          # CSV datasets for training Naive Bayes
│   └── tools/
│       ├── base_tool.py            # Abstract Base Class for system tools
│       └── spotify/                # Spotify Integration Module
│           ├── spotify_tool.py     # Main Spotify routing and ADB logic
│           ├── sqlite_client.py    # Relational caching logic
│           └── chromadb_client.py  # Vector semantic search logic
├── .env                            # Environment variables (Ignored in Git)
└── README.md
```

--- 

## What's next
LARS is actively under developement. Planned features:
- [x] Local ML intent router.
- [x] Build a dual-database caching for Spotify.
- [x] Bypass Spotify active device API limits via ADB.
- [ ] Extract external device management logic into a seperate class (add other devices).
- [ ] Think of a better strategy for selecting which Chroma result should be played.
- [ ] Expand Spotify playback to songs and playlists not included in user's library.
- [ ] Expand toolset (Web Search, Weather, YT/Netflix Playback).
- [ ] Integrate a local LLM generation layer for conversational responses.
- [ ] Integrate both TTS and STT for voice usage.
- [ ] Integrate OpenWakeWord. 
