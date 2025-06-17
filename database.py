# database.py
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

def get_db_connection(db_name):
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints
    logging.info(f"Database connection established to {db_name}")
    return conn

def get_db_connection(db_name):
    conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    logging.info(f"Database connection established to {db_name}")
    return conn

def initialize_database(conn):
    """Creates database tables and adds new columns if they don't exist."""
    cursor = conn.cursor()
    logging.info("Initializing/verifying database schema...")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Categories (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, last_scanned_top_streams TIMESTAMP
    );
    """)

    # Channels Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Channels (
        id TEXT PRIMARY KEY, login TEXT NOT NULL UNIQUE, display_name TEXT,
        description TEXT, profile_image_url TEXT, broadcaster_type TEXT,
        view_count INTEGER, -- Stays for historical reasons, but deprecated by Twitch
        follower_count INTEGER, -- << NEW: For total followers
        created_at TIMESTAMP, first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_fetched_details TIMESTAMP, last_fetched_videos TIMESTAMP
    );
    """)

    # Safely add the new column to existing databases
    try:
        cursor.execute("ALTER TABLE Channels ADD COLUMN follower_count INTEGER;")
        logging.info("Added 'follower_count' column to Channels table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            pass # Column already exists, which is fine
        else:
            raise

    # Videos Table - ADD game_id, game_name
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Videos (
        id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, title TEXT, description TEXT,
        published_at TIMESTAMP, url TEXT, thumbnail_url TEXT, view_count INTEGER,
        duration TEXT, type TEXT, language TEXT,
        game_id TEXT, -- Category ID video was associated with
        game_name TEXT, -- Category Name
        created_at_api TIMESTAMP, fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        muted_segments TEXT, mentions_processed_at TIMESTAMP, -- When mentions were last processed (NULL if not processed)
        FOREIGN KEY (channel_id) REFERENCES Channels (id) ON DELETE CASCADE
        -- Optional: FOREIGN KEY (game_id) REFERENCES Categories (id) ON DELETE SET NULL
    );
    """)
    # Ensure indexes exist
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON Videos (channel_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published_at ON Videos (published_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_mentions_processed ON Videos (mentions_processed_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_game_id ON Videos (game_id);") # Index for new column
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_last_fetched_videos ON Channels (last_fetched_videos);")


    # Collaborations Table (Overall edge summary)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Collaborations (
        channel_id_1 TEXT NOT NULL, channel_id_2 TEXT NOT NULL, -- PK: lower ID first
        collaboration_count INTEGER DEFAULT 0,
        total_collaboration_duration_seconds INTEGER DEFAULT 0,
        latest_collaboration_timestamp TIMESTAMP,
        first_collaboration_timestamp TIMESTAMP,
        last_updated TIMESTAMP,
        PRIMARY KEY (channel_id_1, channel_id_2),
        FOREIGN KEY (channel_id_1) REFERENCES Channels (id) ON DELETE CASCADE,
        FOREIGN KEY (channel_id_2) REFERENCES Channels (id) ON DELETE CASCADE
    );
    """)
    # Ensure indexes exist
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collab_ch1 ON Collaborations (channel_id_1);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collab_ch2 ON Collaborations (channel_id_2);")


    # NEW: Collaboration Context Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS CollaborationContext (
        channel_id_1 TEXT NOT NULL, -- Lower ID first
        channel_id_2 TEXT NOT NULL, -- Higher ID first
        game_id TEXT NOT NULL, -- Use 'UNKNOWN_GAME_ID' if null/empty
        game_name TEXT,
        context_collaboration_count INTEGER DEFAULT 0,
        context_total_duration_seconds INTEGER DEFAULT 0,
        last_updated TIMESTAMP,
        PRIMARY KEY (channel_id_1, channel_id_2, game_id),
        FOREIGN KEY (channel_id_1) REFERENCES Channels (id) ON DELETE CASCADE,
        FOREIGN KEY (channel_id_2) REFERENCES Channels (id) ON DELETE CASCADE
        -- Optional: FOREIGN KEY (game_id) REFERENCES Categories (id) ON DELETE SET NULL
    );
    """)
    # Add index for faster context lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collab_context_game ON CollaborationContext (game_id);")


    conn.commit() # Commit after all schema changes
    logging.info("Database schema initialized/verified successfully.")

# --- Data Saving Functions ---

def save_categories(conn, categories):
    """Saves or ignores category data."""
    cursor = conn.cursor()
    sql = "INSERT OR IGNORE INTO Categories (id, name) VALUES (?, ?)"
    data_to_insert = [(cat['id'], cat['name']) for cat in categories]
    try:
        cursor.executemany(sql, data_to_insert)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error saving categories: {e}")
        conn.rollback()

def update_category_scan_time(conn, category_id):
    """Updates the last scan time for a category."""
    cursor = conn.cursor()
    sql = "UPDATE Categories SET last_scanned_top_streams = ? WHERE id = ?"
    now = datetime.now(timezone.utc)
    try:
        cursor.execute(sql, (now, category_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error updating scan time for category {category_id}: {e}")
        conn.rollback()


def save_channel_basic(conn, channel_data):
     """Saves minimal channel info, primarily for linking videos if full details aren't fetched yet."""
     cursor = conn.cursor()
     sql = """
     INSERT OR IGNORE INTO Channels (id, login, display_name)
     VALUES (?, ?, ?)
     """
     try:
         cursor.execute(sql, (channel_data['id'], channel_data['login'], channel_data['display_name']))
         conn.commit()
         return True
     except sqlite3.Error as e:
         logging.error(f"DB error saving basic channel {channel_data['login']}: {e}")
         conn.rollback()
         return False


def save_channel_details(conn, channel_details):
    """Saves or updates detailed channel information, now including follower_count."""
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    created_at_dt = None
    created_at_str = channel_details.get('created_at')
    if created_at_str:
        try:
            created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except ValueError:
            logging.warning(f"Could not parse channel created_at timestamp: {created_at_str}")

    sql = """
    INSERT INTO Channels (
        id, login, display_name, description, profile_image_url,
        broadcaster_type, view_count, follower_count, -- Added follower_count
        created_at, last_fetched_details
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        login = excluded.login,
        display_name = excluded.display_name,
        description = excluded.description,
        profile_image_url = excluded.profile_image_url,
        broadcaster_type = excluded.broadcaster_type,
        view_count = excluded.view_count,
        follower_count = excluded.follower_count, -- Added follower_count
        created_at = COALESCE(excluded.created_at, created_at),
        last_fetched_details = excluded.last_fetched_details;
    """
    data = (
        channel_details['id'],
        channel_details['login'],
        channel_details.get('display_name'),
        channel_details.get('description'),
        channel_details.get('profile_image_url'),
        channel_details.get('broadcaster_type'),
        channel_details.get('view_count', 0), # Default deprecated field to 0
        channel_details.get('follower_count'), # Get the new field
        created_at_dt,
        now
    )
    try:
        cursor.execute(sql, data)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error saving channel details for {channel_details['login']}: {e}")
        conn.rollback()
        raise

def save_videos(conn, videos):
    """Saves or ignores video data including game_id and game_name."""
    cursor = conn.cursor()
    # Include game_id, game_name in the INSERT
    sql = """
    INSERT OR IGNORE INTO Videos (
        id, channel_id, title, description, published_at, url, thumbnail_url,
        view_count, duration, type, language, game_id, game_name,
        created_at_api, muted_segments
        -- mentions_processed_at defaults to NULL
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    data_to_insert = []
    for video in videos:
        published_at_str = video.get('published_at'); created_at_api_str = video.get('created_at')
        published_at_dt = None; created_at_api_dt = None
        video_id_for_log = video.get('id', 'UNKNOWN_ID')

        if published_at_str:
            try: published_at_dt = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            except ValueError: logging.warning(f"Could not parse video published_at: {published_at_str} for video {video_id_for_log}")
        if created_at_api_str:
            try: created_at_api_dt = datetime.fromisoformat(created_at_api_str.replace('Z', '+00:00'))
            except ValueError: logging.warning(f"Could not parse video created_at_api: {created_at_api_str} for video {video_id_for_log}")
        muted_segments_json = None
        if video.get('muted_segments'):
            try: muted_segments_json = json.dumps(video['muted_segments'])
            except TypeError: logging.warning(f"Could not serialize muted_segments for video {video_id_for_log}")

        data_to_insert.append((
            video['id'], video['user_id'], video.get('title'), video.get('description'),
            published_at_dt, video.get('url'), video.get('thumbnail_url'),
            video.get('view_count'), video.get('duration'), video.get('type'),
            video.get('language'),
            video.get('game_id'), # Add game_id
            video.get('game_name'), # Add game_name
            created_at_api_dt, muted_segments_json
        ))

    try:
        cursor.executemany(sql, data_to_insert)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error saving videos: {e}")
        conn.rollback()

def update_channel_video_fetch_time(conn, channel_id):
    """Updates the last time videos were fetched for a channel."""
    cursor = conn.cursor()
    sql = "UPDATE Channels SET last_fetched_videos = ? WHERE id = ?"
    now = datetime.now(timezone.utc)
    try:
        cursor.execute(sql, (now, channel_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error updating video fetch time for channel {channel_id}: {e}")
        conn.rollback()


def upsert_collaboration_edge(conn, channel_a_id, channel_b_id, video_published_at, video_duration_seconds):
    """
    Inserts or updates a collaboration edge between two channels within the current transaction.
    Ensures channel_id_1 < channel_id_2 for consistency. Re-raises errors.
    """
    if channel_a_id == channel_b_id: return

    id1 = min(channel_a_id, channel_b_id)
    id2 = max(channel_a_id, channel_b_id)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    duration = video_duration_seconds if video_duration_seconds is not None else 0
    published_at_ts = video_published_at # Assume datetime object

    sql = """
    INSERT INTO Collaborations (
        channel_id_1, channel_id_2, collaboration_count,
        total_collaboration_duration_seconds, latest_collaboration_timestamp,
        first_collaboration_timestamp, last_updated
    ) VALUES (?, ?, 1, ?, ?, ?, ?)
    ON CONFLICT(channel_id_1, channel_id_2) DO UPDATE SET
        collaboration_count = collaboration_count + 1,
        total_collaboration_duration_seconds = total_collaboration_duration_seconds + excluded.total_collaboration_duration_seconds,
        latest_collaboration_timestamp = CASE
            WHEN excluded.latest_collaboration_timestamp > latest_collaboration_timestamp
            THEN excluded.latest_collaboration_timestamp
            ELSE latest_collaboration_timestamp
        END,
        -- Keep the original first timestamp (important!)
        first_collaboration_timestamp = COALESCE(first_collaboration_timestamp, excluded.first_collaboration_timestamp),
        last_updated = excluded.last_updated;
    """
    try:
        cursor.execute(sql, (
            id1, id2, duration, published_at_ts, published_at_ts, now
        ))
        # NO COMMIT / ROLLBACK HERE - Handled by caller's transaction
    except sqlite3.Error as e:
        logging.error(f"DB error during upsert_collaboration_edge for {id1}-{id2}: {e}")
        raise # Re-raise the error to be caught by the transaction handler
    except Exception as e:
        logging.error(f"Unexpected error upserting collaboration {id1}-{id2}: {e}")
        raise


def upsert_collaboration_context(conn, channel_id_1, channel_id_2, game_id, game_name, video_duration_seconds):
    """Inserts/updates collaboration context for a specific game within caller's transaction."""
    id1 = min(channel_id_1, channel_id_2)
    id2 = max(channel_id_1, channel_id_2)
    # Handle null/empty game_id consistently
    effective_game_id = game_id if game_id and game_id.strip() else "UNKNOWN_GAME_ID"
    effective_game_name = game_name if effective_game_id != "UNKNOWN_GAME_ID" and game_name and game_name.strip() else "Unknown/Not Specified"

    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    duration = video_duration_seconds if video_duration_seconds is not None else 0

    sql = """
    INSERT INTO CollaborationContext (
        channel_id_1, channel_id_2, game_id, game_name,
        context_collaboration_count, context_total_duration_seconds, last_updated
    ) VALUES (?, ?, ?, ?, 1, ?, ?)
    ON CONFLICT(channel_id_1, channel_id_2, game_id) DO UPDATE SET
        context_collaboration_count = context_collaboration_count + 1,
        context_total_duration_seconds = context_total_duration_seconds + excluded.context_total_duration_seconds,
        game_name = COALESCE(excluded.game_name, game_name), -- Update name if new one provided and valid
        last_updated = excluded.last_updated;
    """
    try:
        cursor.execute(sql, (
            id1, id2, effective_game_id, effective_game_name, duration, now
        ))
        # NO COMMIT / ROLLBACK HERE
    except sqlite3.Error as e:
        logging.error(f"DB error during upsert_collaboration_context for {id1}-{id2} game {effective_game_id}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error upserting collab context for {id1}-{id2} game {effective_game_id}: {e}")
        raise


def mark_video_mentions_processed(conn, video_id):
    """
    Sets the mentions_processed_at timestamp for a given video ID within the current transaction.
    Re-raises errors.
    """
    cursor = conn.cursor()
    sql = "UPDATE Videos SET mentions_processed_at = ? WHERE id = ?"
    now = datetime.now(timezone.utc)
    try:
        cursor.execute(sql, (now, video_id))
        # NO COMMIT / ROLLBACK HERE - Handled by caller's transaction
    except sqlite3.Error as e:
        logging.error(f"DB error during mark_video_mentions_processed for {video_id}: {e}")
        raise # Re-raise the error
    except Exception as e:
        logging.error(f"Unexpected error marking mentions processed for {video_id}: {e}")
        raise


# --- Data Querying Functions ---

def get_categories_to_scan(conn, limit):
    """Gets categories ordered by oldest scan time first."""
    cursor = conn.cursor()
    sql = "SELECT id, name FROM Categories ORDER BY last_scanned_top_streams ASC NULLS FIRST LIMIT ?"
    cursor.execute(sql, (limit,))
    return cursor.fetchall()

def check_channel_needs_update(conn, channel_id, details_max_age_days):
    """Checks if channel details exist and are older than the specified age."""
    cursor = conn.cursor()
    sql = "SELECT last_fetched_details FROM Channels WHERE id = ?"
    cursor.execute(sql, (channel_id,))
    result = cursor.fetchone()
    if not result or not result['last_fetched_details']:
        return True
    last_fetched = result['last_fetched_details']
    # Ensure last_fetched is datetime for comparison
    if isinstance(last_fetched, str):
        try: last_fetched = datetime.fromisoformat(last_fetched).replace(tzinfo=timezone.utc) # Assume UTC if not tz-aware
        except ValueError: return True # Treat parse error as needing update
    elif isinstance(last_fetched, datetime) and last_fetched.tzinfo is None : # If datetime but naive
        last_fetched = last_fetched.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) > (last_fetched + timedelta(days=details_max_age_days))

def get_channels_to_fetch_videos(conn, videos_max_age_days, limit=50):
    """Gets channels whose videos haven't been checked recently."""
    cursor = conn.cursor()
    threshold_date = datetime.now(timezone.utc) - timedelta(days=videos_max_age_days)
    sql = """
    SELECT id, login FROM Channels
    WHERE last_fetched_videos IS NULL OR last_fetched_videos < ?
    ORDER BY last_fetched_videos ASC NULLS FIRST
    LIMIT ?
    """
    cursor.execute(sql, (threshold_date, limit))
    return cursor.fetchall()

def get_latest_video_date_for_channel(conn, channel_id):
     """Finds the publish date of the most recent video stored for a channel."""
     cursor = conn.cursor()
     sql = "SELECT MAX(published_at) as latest_date FROM Videos WHERE channel_id = ?"
     cursor.execute(sql, (channel_id,))
     result = cursor.fetchone()
     if result and result['latest_date']:
         latest_date = result['latest_date']
         # Ensure it's a datetime object with timezone for comparison
         if isinstance(latest_date, str):
             try: latest_date = datetime.fromisoformat(latest_date.replace('Z', '+00:00'))
             except ValueError: return None
         elif isinstance(latest_date, datetime):
             if latest_date.tzinfo is None:
                 latest_date = latest_date.replace(tzinfo=timezone.utc)
             return latest_date
         return latest_date # Should be tz-aware datetime
     return None

def get_unprocessed_videos_batch(conn, batch_size):
    """Fetches a batch of videos where mentions haven't been processed. Includes game_id/name."""
    cursor = conn.cursor()
    sql = """
    SELECT id, channel_id, title, description, published_at, duration, game_id, game_name
    FROM Videos
    WHERE mentions_processed_at IS NULL
    ORDER BY fetched_at ASC -- Process videos shortly after they are added
    LIMIT ?
    """
    try:
        cursor.execute(sql, (batch_size,))
        return cursor.fetchall() # Returns list of Row objects
    except sqlite3.Error as e:
        logging.error(f"Database error fetching unprocessed videos batch: {e}")
        return []

def get_all_channel_ids(conn):
    """Fetches all channel IDs from the Channels table."""
    cursor = conn.cursor()
    sql = "SELECT id FROM Channels"
    try:
        cursor.execute(sql)
        return [row['id'] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Database error fetching all channel IDs: {e}")
        return []

# Add this new function to database.py

def get_stale_channels_for_refresh(conn, limit):
    """
    Gets a list of channels that are the "stalest" based on when their videos were last fetched.
    Channels that have never been fetched (NULL) are prioritized first.
    """
    cursor = conn.cursor()
    # ORDER BY last_fetched_videos ASC puts oldest dates first.
    # NULLS FIRST ensures channels we've never seen get top priority.
    sql = """
    SELECT id, login FROM Channels
    ORDER BY last_fetched_videos ASC NULLS FIRST
    LIMIT ?
    """
    try:
        cursor.execute(sql, (limit,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Database error fetching stale channels for refresh: {e}")
        return []

if __name__ == '__main__':
    import config
    db_conn = get_db_connection(config.DATABASE_NAME)
    initialize_database(db_conn)
    db_conn.close()
    logging.info("Database module executed: Schema initialized/verified (if needed).")