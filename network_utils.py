# network_utils.py
import re
import logging
import sqlite3

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# Regex to find potential Twitch logins after an @ sign
# Logins are 4-25 characters, alphanumeric + underscore
MENTION_REGEX = re.compile(r'@([a-zA-Z0-9_]{4,25})')

def extract_mentions(text):
    """Extracts potential Twitch channel logins mentioned in text (e.g., '@username')."""
    if not text or not isinstance(text, str):
        return []
    # Find all matches and convert to lowercase for consistent matching
    potential_logins = [match.lower() for match in MENTION_REGEX.findall(text)]
    # Filter out common non-usernames if needed, e.g. @everyone (though unlikely in titles)
    # Example: known_non_users = {'everyone', 'here', 'channel'}
    # potential_logins = [p for p in potential_logins if p not in known_non_users]
    return list(set(potential_logins)) # Return unique logins

def find_mentioned_channel_ids(logins, db_conn):
    """
    Queries the database to find channel IDs for a list of mentioned logins.

    Args:
        logins (list): A list of lowercase potential channel logins.
        db_conn: An active SQLite database connection.

    Returns:
        tuple: (found_channels, not_found_logins)
               - found_channels (dict): {lowercase_login: channel_id}
               - not_found_logins (list): [lowercase_login]
    """
    if not logins:
        return {}, []

    found_channels = {}
    # Ensure input is unique lowercase logins and are strings
    logins_set = set(l.lower() for l in logins if isinstance(l, str) and l)
    if not logins_set: return {}, [] # Return empty if no valid logins after filtering

    not_found_logins_set = set(logins_set) # Start assuming all are not found
    cursor = db_conn.cursor()

    try:
        # Create placeholders for the query (?, ?, ?)
        placeholders = ', '.join('?' for _ in logins_set)
        # Query using LOWER(login) for case-insensitive comparison
        sql = f"SELECT id, login FROM Channels WHERE LOWER(login) IN ({placeholders})"

        # Pass the list version of the set to ensure consistent order for SQL params if DB requires
        cursor.execute(sql, list(logins_set))
        results = cursor.fetchall() # List of sqlite3.Row objects

        for row in results:
            # Store with the lowercase login as key for easy lookup
            login_lower = row['login'].lower() # Ensure retrieved login is also lowercased for matching
            found_channels[login_lower] = row['id']
            # If found, remove from the not_found set
            if login_lower in not_found_logins_set:
                not_found_logins_set.remove(login_lower)

    except sqlite3.Error as e:
        logging.error(f"Database error finding mentioned channel IDs: {e}")
        # On error, assume none were found reliably (return all original valid logins as not found)
        return {}, list(logins_set)
    except Exception as e:
        logging.error(f"Unexpected error in find_mentioned_channel_ids: {e}", exc_info=True)
        return {}, list(logins_set)


    return found_channels, list(not_found_logins_set)

if __name__ == '__main__':
    # Example Usage
    sample_title = "Playing cool game with @AwesomeStreamer1 and @another_user_123! Also @NoExist. Check them out. Invalid @usr mention."
    mentions = extract_mentions(sample_title)
    print(f"Extracted mentions: {mentions}")

    # Dummy connection and data for testing find_mentioned_channel_ids
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row # Enable column name access
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE Channels (id TEXT PRIMARY KEY, login TEXT UNIQUE);")
    cursor.execute("INSERT INTO Channels (id, login) VALUES ('1001', 'awesomestreamer1');")
    cursor.execute("INSERT INTO Channels (id, login) VALUES ('1002', 'another_user_123');")
    conn.commit()

    print(f"Mentions to check against DB: {mentions}")

    found, not_found = find_mentioned_channel_ids(mentions, conn)
    print(f"\nValidated mentions found in DB: {found}")
    print(f"Mentions NOT found in DB: {not_found}")

    conn.close()