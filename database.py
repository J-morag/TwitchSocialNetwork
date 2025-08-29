# database.py
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


def get_db_connection(db_name):
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    logging.info(f"Database connection established to {db_name}")
    return conn


def initialize_database(conn):
    """Creates database tables if they don't exist."""
    cursor = conn.cursor()
    logging.info("Initializing/verifying database schema...")

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Categories
                   (
                       id
                       TEXT
                       PRIMARY
                       KEY,
                       name
                       TEXT
                       NOT
                       NULL,
                       last_scanned_top_streams
                       TIMESTAMP
                   );
                   """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Channels
                   (
                       id
                       TEXT
                       PRIMARY
                       KEY,
                       login
                       TEXT
                       NOT
                       NULL
                       UNIQUE,
                       display_name
                       TEXT,
                       description
                       TEXT,
                       profile_image_url
                       TEXT,
                       broadcaster_type
                       TEXT,
                       view_count
                       INTEGER,
                       follower_count
                       INTEGER,
                       tags
                       TEXT, 
                       created_at
                       TIMESTAMP,
                       first_seen
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       last_fetched_details
                       TIMESTAMP,
                       last_fetched_videos
                       TIMESTAMP
                   );
                   """)

    # Safely add the new tags column to existing databases
    try:
        cursor.execute("ALTER TABLE Channels ADD COLUMN tags TEXT;")
        logging.info("Added 'tags' column to Channels table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            pass  # Column already exists, which is fine
        else:
            raise

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Videos
                   (
                       id
                       TEXT
                       PRIMARY
                       KEY,
                       channel_id
                       TEXT
                       NOT
                       NULL,
                       title
                       TEXT,
                       description
                       TEXT,
                       published_at
                       TIMESTAMP,
                       url
                       TEXT,
                       thumbnail_url
                       TEXT,
                       view_count
                       INTEGER,
                       duration
                       TEXT,
                       type
                       TEXT,
                       language
                       TEXT,
                       created_at_api
                       TIMESTAMP,
                       fetched_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       muted_segments
                       TEXT,
                       mentions_processed_at
                       TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       channel_id
                   ) REFERENCES Channels
                   (
                       id
                   ) ON DELETE CASCADE
                       );
                   """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON Videos (channel_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published_at ON Videos (published_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_mentions_processed ON Videos (mentions_processed_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_last_fetched_videos ON Channels (last_fetched_videos);")

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Collaborations
                   (
                       channel_id_1
                       TEXT
                       NOT
                       NULL,
                       channel_id_2
                       TEXT
                       NOT
                       NULL,
                       collaboration_count
                       INTEGER
                       DEFAULT
                       0,
                       total_collaboration_duration_seconds
                       INTEGER
                       DEFAULT
                       0,
                       latest_collaboration_timestamp
                       TIMESTAMP,
                       first_collaboration_timestamp
                       TIMESTAMP,
                       last_updated
                       TIMESTAMP,
                       PRIMARY
                       KEY
                   (
                       channel_id_1,
                       channel_id_2
                   ),
                       FOREIGN KEY
                   (
                       channel_id_1
                   ) REFERENCES Channels
                   (
                       id
                   ) ON DELETE CASCADE,
                       FOREIGN KEY
                   (
                       channel_id_2
                   ) REFERENCES Channels
                   (
                       id
                   )
                     ON DELETE CASCADE
                       );
                   """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collab_ch1 ON Collaborations (channel_id_1);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collab_ch2 ON Collaborations (channel_id_2);")

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Mentions
                   (
                       source_channel_id
                       TEXT
                       NOT
                       NULL,
                       target_channel_id
                       TEXT
                       NOT
                       NULL,
                       video_id
                       TEXT
                       NOT
                       NULL,
                       mention_timestamp
                       TIMESTAMP,
                       PRIMARY
                       KEY
                   (
                       source_channel_id,
                       target_channel_id,
                       video_id
                   ),
                       FOREIGN KEY
                   (
                       source_channel_id
                   ) REFERENCES Channels
                   (
                       id
                   ) ON DELETE CASCADE,
                       FOREIGN KEY
                   (
                       target_channel_id
                   ) REFERENCES Channels
                   (
                       id
                   )
                     ON DELETE CASCADE,
                       FOREIGN KEY
                   (
                       video_id
                   ) REFERENCES Videos
                   (
                       id
                   )
                     ON DELETE CASCADE
                       );
                   """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_video_id ON Mentions (video_id);")

    # Drop the obsolete CollaborationContext table if it exists from a previous version
    cursor.execute("DROP TABLE IF EXISTS CollaborationContext;")

    # Safely add the follower_count column to existing databases from before the change
    try:
        cursor.execute("ALTER TABLE Channels ADD COLUMN follower_count INTEGER;")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise  # Re-raise error if it's not the expected one

    conn.commit()
    logging.info("Database schema initialized/verified successfully.")


def save_categories(conn, categories):
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
    cursor = conn.cursor()
    sql = "INSERT OR IGNORE INTO Channels (id, login, display_name) VALUES (?, ?, ?)"
    try:
        cursor.execute(sql, (channel_data['id'], channel_data['login'], channel_data['display_name']))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"DB error saving basic channel {channel_data['login']}: {e}")
        conn.rollback()
        return False


def update_channel_detail_fetch_time(conn, channel_id):
    """Updates the last_fetched_details timestamp for a channel."""
    cursor = conn.cursor()
    sql = "UPDATE Channels SET last_fetched_details = ? WHERE id = ?"
    now = datetime.now(timezone.utc)
    try:
        cursor.execute(sql, (now, channel_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error updating detail fetch time for channel {channel_id}: {e}")
        conn.rollback()


def save_channel_details(conn, channel_details):
    """
    Saves or updates detailed channel information using a legacy-compatible
    two-step INSERT OR IGNORE + UPDATE method to ensure maximum compatibility.
    """
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    created_at_dt = None
    created_at_str = channel_details.get('created_at')
    if created_at_str:
        try:
            created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except ValueError:
            logging.warning(f"Could not parse channel created_at timestamp: {created_at_str}")

    tags_json = json.dumps(channel_details.get('tags')) if channel_details.get('tags') is not None else None

    # Step 1: Insert the record if it doesn't exist. If it does, do nothing.
    insert_sql = """
    INSERT OR IGNORE INTO Channels (
        id, login, display_name, description, profile_image_url,
        broadcaster_type, view_count, follower_count, tags,
        created_at, last_fetched_details
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    insert_data = (
        channel_details['id'], channel_details['login'],
        channel_details.get('display_name'), channel_details.get('description'),
        channel_details.get('profile_image_url'), channel_details.get('broadcaster_type'),
        channel_details.get('view_count', 0), channel_details.get('follower_count'),
        tags_json, created_at_dt, now
    )

    # Step 2: Update the record. This will affect the row whether it was
    # just inserted or if it already existed.
    update_sql = """
    UPDATE Channels SET
        login = ?, 
        display_name = ?, 
        description = ?, 
        profile_image_url = ?,
        broadcaster_type = ?, 
        view_count = ?, 
        follower_count = ?, 
        tags = ?,
        -- Only update created_at if it's currently NULL to preserve original creation date
        created_at = COALESCE(created_at, ?),
        last_fetched_details = ?
    WHERE id = ?;
    """
    update_data = (
        channel_details['login'],
        channel_details.get('display_name'),
        channel_details.get('description'),
        channel_details.get('profile_image_url'),
        channel_details.get('broadcaster_type'),
        channel_details.get('view_count', 0),
        channel_details.get('follower_count'),
        tags_json,
        created_at_dt,
        now,
        channel_details['id'] # For the WHERE clause
    )

    try:
        # Execute both statements in a single transaction
        cursor.execute(insert_sql, insert_data)
        cursor.execute(update_sql, update_data)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error saving channel details for {channel_details['login']}: {e}")
        conn.rollback()
        raise


def save_videos(conn, videos):
    cursor = conn.cursor()
    sql = """
          INSERT \
          OR IGNORE INTO Videos (
        id, channel_id, title, description, published_at, url, thumbnail_url,
        view_count, duration, type, language, created_at_api, muted_segments
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
          """
    data_to_insert = []
    for video in videos:
        published_at_str = video.get('published_at');
        created_at_api_str = video.get('created_at')
        published_at_dt = None;
        created_at_api_dt = None
        video_id_for_log = video.get('id', 'UNKNOWN_ID')

        if published_at_str:
            try:
                published_at_dt = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            except ValueError:
                logging.warning(f"Could not parse video published_at: {published_at_str} for video {video_id_for_log}")
        if created_at_api_str:
            try:
                created_at_api_dt = datetime.fromisoformat(created_at_api_str.replace('Z', '+00:00'))
            except ValueError:
                logging.warning(
                    f"Could not parse video created_at_api: {created_at_api_str} for video {video_id_for_log}")

        muted_segments_json = None
        if video.get('muted_segments'):
            try:
                muted_segments_json = json.dumps(video['muted_segments'])
            except TypeError:
                logging.warning(f"Could not serialize muted_segments for video {video_id_for_log}")

        data_to_insert.append((
            video['id'], video['user_id'], video.get('title'), video.get('description'),
            published_at_dt, video.get('url'), video.get('thumbnail_url'),
            video.get('view_count'), video.get('duration'), video.get('type'),
            video.get('language'), created_at_api_dt, muted_segments_json
        ))
    try:
        cursor.executemany(sql, data_to_insert)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error saving videos: {e}")
        conn.rollback()


def update_channel_video_fetch_time(conn, channel_id):
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
    if channel_a_id == channel_b_id: return
    id1 = min(channel_a_id, channel_b_id)
    id2 = max(channel_a_id, channel_b_id)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    duration = video_duration_seconds if video_duration_seconds is not None else 0
    published_at_ts = video_published_at

    sql = """
          INSERT INTO Collaborations (channel_id_1, channel_id_2, collaboration_count, \
                                      total_collaboration_duration_seconds, \
                                      latest_collaboration_timestamp, first_collaboration_timestamp, last_updated) \
          VALUES (?, ?, 1, ?, ?, ?, ?) ON CONFLICT(channel_id_1, channel_id_2) DO \
          UPDATE SET
              collaboration_count = collaboration_count + 1, \
              total_collaboration_duration_seconds = total_collaboration_duration_seconds + excluded.total_collaboration_duration_seconds, \
              latest_collaboration_timestamp = CASE WHEN excluded.latest_collaboration_timestamp > latest_collaboration_timestamp THEN excluded.latest_collaboration_timestamp ELSE latest_collaboration_timestamp \
          END,
        first_collaboration_timestamp = COALESCE(first_collaboration_timestamp, excluded.first_collaboration_timestamp),
        last_updated = excluded.last_updated; \
          """
    try:
        cursor.execute(sql, (id1, id2, duration, published_at_ts, published_at_ts, now))
    except sqlite3.Error as e:
        logging.error(f"DB error during upsert_collaboration_edge for {id1}-{id2}: {e}")
        raise


def add_mentions(conn, mention_data_list):
    if not mention_data_list: return
    cursor = conn.cursor()
    sql = "INSERT OR IGNORE INTO Mentions (source_channel_id, target_channel_id, video_id, mention_timestamp) VALUES (?, ?, ?, ?)"
    try:
        cursor.executemany(sql, mention_data_list)
    except sqlite3.Error as e:
        logging.error(f"DB error during bulk insert into Mentions table: {e}")
        raise


def mark_video_mentions_processed(conn, video_id):
    cursor = conn.cursor()
    sql = "UPDATE Videos SET mentions_processed_at = ? WHERE id = ?"
    now = datetime.now(timezone.utc)
    try:
        cursor.execute(sql, (now, video_id))
    except sqlite3.Error as e:
        logging.error(f"DB error during mark_video_mentions_processed for {video_id}: {e}")
        raise


# --- Data Querying Functions ---

def get_categories_to_scan(conn, limit):
    cursor = conn.cursor()
    sql = "SELECT id, name FROM Categories ORDER BY last_scanned_top_streams ASC NULLS FIRST LIMIT ?"
    cursor.execute(sql, (limit,))
    return cursor.fetchall()


def check_channel_needs_update(conn, channel_id, details_max_age_days):
    cursor = conn.cursor()
    sql = "SELECT last_fetched_details FROM Channels WHERE id = ?"
    cursor.execute(sql, (channel_id,))
    result = cursor.fetchone()
    if not result or not result['last_fetched_details']: return True
    last_fetched = result['last_fetched_details']
    if isinstance(last_fetched, str):
        try:
            last_fetched = datetime.fromisoformat(last_fetched).replace(tzinfo=timezone.utc)
        except ValueError:
            return True
    elif isinstance(last_fetched, datetime) and last_fetched.tzinfo is None:
        last_fetched = last_fetched.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > (last_fetched + timedelta(days=details_max_age_days))


def get_stale_channels_for_refresh(conn, limit):
    cursor = conn.cursor()
    sql = "SELECT id, login FROM Channels ORDER BY last_fetched_videos ASC NULLS FIRST LIMIT ?"
    try:
        cursor.execute(sql, (limit,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Database error fetching stale channels for refresh: {e}")
        return []


def get_latest_video_date_for_channel(conn, channel_id):
    cursor = conn.cursor()
    sql = "SELECT MAX(published_at) as latest_date FROM Videos WHERE channel_id = ?"
    cursor.execute(sql, (channel_id,))
    result = cursor.fetchone()
    if result and result['latest_date']:
        latest_date = result['latest_date']
        if isinstance(latest_date, str):
            try:
                latest_date = datetime.fromisoformat(latest_date.replace('Z', '+00:00'))
            except ValueError:
                return None
        if isinstance(latest_date, datetime) and latest_date.tzinfo is None:
            latest_date = latest_date.replace(tzinfo=timezone.utc)
        return latest_date
    return None


def get_unprocessed_videos_batch(conn, batch_size):
    cursor = conn.cursor()
    sql = "SELECT id, channel_id, title, description, published_at, duration FROM Videos WHERE mentions_processed_at IS NULL ORDER BY fetched_at ASC LIMIT ?"
    try:
        cursor.execute(sql, (batch_size,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Database error fetching unprocessed videos batch: {e}")
        return []


def get_all_channel_ids(conn):
    cursor = conn.cursor()
    sql = "SELECT id FROM Channels"
    try:
        cursor.execute(sql)
        return [row['id'] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Database error fetching all channel IDs: {e}")
        return []