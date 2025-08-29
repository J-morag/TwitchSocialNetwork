# config.py
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# --- Twitch API Credentials ---
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

# --- API Endpoints ---
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_API_BASE_URL = "https://api.twitch.tv/helix"

# --- Database Configuration ---
DATABASE_NAME = "twitch_data.db"

# --- Data Collection Parameters ---
# These control how much new data is fetched in each cycle
NUM_TOP_CATEGORIES = 50  # Number of top categories to fetch
NUM_STREAMS_PER_CATEGORY = 50 # Number of top streams to fetch per category
REFETCH_CHANNEL_DETAILS_DAYS = 7 # How often to re-fetch full channel details
REFETCH_CHANNEL_VIDEOS_DAYS = 2  # How often to check for new videos for a channel

MENTION_PROC_BATCH_SIZE = 500  # Videos per batch for mention processing
MENTION_PROC_MAX_BATCHES = 100 # Max mention processing batches per notebook run

REFRESH_CYCLE_CHANNELS = 500   # Number of channels to refresh details/videos for per run

# Optional: Fetch videos only published after a certain date (None to fetch all initially)
# FETCH_VIDEOS_AFTER = datetime(2024, 1, 1, tzinfo=timezone.utc) # Example date
FETCH_VIDEOS_AFTER = None


# --- Network Analysis Thresholds ---
# These control filtering for network visualization & community detection
# Applied IN MEMORY, does NOT delete data from the database.
NETWORK_MIN_COLLABORATION_COUNT = 2       # Edges with fewer collabs than this are ignored in analysis.
NETWORK_MIN_FOLLOWER_COUNT = 1000     # Channels with fewer total followers are ignored in analysis.
NETWORK_MIN_CHANNEL_VIDEO_COUNT = 5       # Channels with fewer videos are ignored in analysis.
# For subgraph visualization specifically
NETWORK_VIZ_TOP_N_CHANNELS_BY_DEGREE = 50 # How many top channels (by degree) to initially pick for subgraph
NETWORK_VIZ_MAX_SUBGRAPH_NODES = 1000       # Max total nodes in the displayed subgraph
NETWORK_DURATION_OUTLIER_WEEKS = 1 # Set threshold to 1 week

# --- Validation ---
if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET or TWITCH_CLIENT_ID == "your_actual_client_id_from_twitch_developer_console":
    raise ValueError("CRITICAL: TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET must be set "
                     "in environment variables or a .env file with your actual credentials.")

# Function to print configuration values (can be called in the notebook)
def print_config():
    print("--- Configuration Settings ---")
    settings = {
        "API & Database": {
            "DATABASE_NAME": DATABASE_NAME,
        },
        "Data Collection": {
            "NUM_TOP_CATEGORIES": NUM_TOP_CATEGORIES,
            "NUM_STREAMS_PER_CATEGORY": NUM_STREAMS_PER_CATEGORY,
            "REFETCH_CHANNEL_DETAILS_DAYS": REFETCH_CHANNEL_DETAILS_DAYS,
            "REFETCH_CHANNEL_VIDEOS_DAYS": REFETCH_CHANNEL_VIDEOS_DAYS,
            "MENTION_PROC_BATCH_SIZE": MENTION_PROC_BATCH_SIZE,
            "MENTION_PROC_MAX_BATCHES": MENTION_PROC_MAX_BATCHES,
            "REFRESH_CYCLE_CHANNELS": REFRESH_CYCLE_CHANNELS,
            "FETCH_VIDEOS_AFTER": FETCH_VIDEOS_AFTER,
        },
        "Network Analysis Thresholds": {
            "NETWORK_MIN_COLLABORATION_COUNT": NETWORK_MIN_COLLABORATION_COUNT,
            "NETWORK_MIN_FOLLOWER_COUNT": NETWORK_MIN_FOLLOWER_COUNT,
            "NETWORK_MIN_CHANNEL_VIDEO_COUNT": NETWORK_MIN_CHANNEL_VIDEO_COUNT,
            "NETWORK_VIZ_TOP_N_CHANNELS_BY_DEGREE": NETWORK_VIZ_TOP_N_CHANNELS_BY_DEGREE,
            "NETWORK_VIZ_MAX_SUBGRAPH_NODES": NETWORK_VIZ_MAX_SUBGRAPH_NODES,
        }
    }
    for section, params in settings.items():
        print(f"\n[{section}]")
        for key, value in params.items():
            print(f"  {key}: {value}")
    print("-" * 28)

if __name__ == '__main__':
    print_config() # Example of printing if run directly
else:
    # This will print when the module is imported by the notebook
    print("Configuration module 'config.py' loaded.")
    if TWITCH_CLIENT_ID == "your_actual_client_id_from_twitch_developer_console" or \
       TWITCH_CLIENT_SECRET == "your_actual_client_secret_from_twitch_developer_console":
        print("\nWARNING: Twitch API credentials in config.py appear to be placeholders.")
        print("Please update your .env file with actual Client ID and Secret.\n")