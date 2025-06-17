# twitch_api.py
import requests
import time
import logging
from datetime import datetime, timezone, timedelta # Ensure timedelta is imported

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

class TwitchAPIClient:
    def __init__(self, client_id, client_secret, auth_url, base_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.base_url = base_url
        self._access_token = None
        self._token_expires_at = datetime.now(timezone.utc) # Initialize past expiry
        self._session = requests.Session() # Use a session for potential connection pooling

    def _get_headers(self):
        """Gets headers required for API calls, refreshing token if necessary."""
        if not self._access_token or datetime.now(timezone.utc) >= self._token_expires_at:
            logging.info("Access token expired or missing. Requesting new token...")
            if not self._authenticate():
                # Allow one immediate retry of authentication if it fails initially
                time.sleep(1) # Brief pause
                if not self._authenticate():
                    raise Exception("Failed to authenticate with Twitch API after retry.")
        return {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self._access_token}'
        }

    def _authenticate(self):
        """Fetches a new App Access Token from Twitch."""
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        response = None # Define response here to ensure it's available in except block
        try:
            response = self._session.post(self.auth_url, data=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            self._access_token = data['access_token']
            expires_in = data.get('expires_in', 3600) # Default to 1 hour if not provided
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300) # 5 min buffer
            logging.info(f"Successfully obtained new access token. Expires around {self._token_expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Error obtaining Twitch access token: {e}")
            if response is not None:
                logging.error(f"Auth Response Status: {response.status_code}")
                logging.error(f"Auth Response Body: {response.text}")
            self._access_token = None # Ensure token is cleared on failure
            return False
        except KeyError: # If 'access_token' or 'expires_in' is missing from response
            logging.error(f"Unexpected response format during authentication: {response.text if response else 'No response'}")
            self._access_token = None
            return False
        except Exception as e: # Catch any other unexpected errors
             logging.error(f"An unexpected error occurred during authentication: {e}")
             self._access_token = None
             return False


    def _make_request(self, method, endpoint, params=None, max_retries=3, **kwargs):
        """Makes an API request, handling rate limits and retries."""
        url = f"{self.base_url}{endpoint}"
        retries = 0
        response = None # Define response here
        while retries <= max_retries:
            try:
                headers = self._get_headers() # Get fresh headers (and token if needed)
                response = self._session.request(method, url, headers=headers, params=params, timeout=15, **kwargs)

                remaining_requests = response.headers.get('Ratelimit-Remaining')
                # Optional: logging.debug(f"Rate limit remaining: {remaining_requests}")

                if response.status_code == 429: # Rate limit hit
                    reset_timestamp = response.headers.get('Ratelimit-Reset')
                    wait_time = 15 # Default wait time if reset header is missing/invalid
                    if reset_timestamp:
                        try:
                            reset_time_dt = datetime.fromtimestamp(int(reset_timestamp), timezone.utc)
                            current_time_utc = datetime.now(timezone.utc)
                            wait_seconds = (reset_time_dt - current_time_utc).total_seconds()
                            wait_time = max(1, wait_seconds + 1) # Add 1s buffer, ensure positive
                        except (ValueError, TypeError):
                            logging.warning(f"Could not parse RateLimit-Reset header value: {reset_timestamp}")
                    logging.warning(f"Rate limit hit (429) for {url}. Waiting for {wait_time:.2f} seconds before retrying (Attempt {retries+1}/{max_retries})...")
                    time.sleep(wait_time)
                    retries += 1
                    continue # Retry the request

                response.raise_for_status() # Raise HTTPError for other bad responses (4xx, 5xx client/server errors)
                return response.json() # Return parsed JSON on success

            except requests.exceptions.Timeout:
                logging.warning(f"Request timed out for {method} {url}. Retrying ({retries+1}/{max_retries}) after {2**retries}s...")
                time.sleep(2 ** retries) # Exponential backoff for timeouts
                retries += 1
            except requests.exceptions.RequestException as e: # Covers other network issues, non-HTTP errors
                 logging.error(f"Request failed for {method} {url}: {e}")
                 if response is not None: # If we got a response object despite exception
                    logging.error(f" -> Response Status: {response.status_code}, Body: {response.text}")
                    if response.status_code == 401: # Unauthorized - token might be stale
                         logging.warning("Received 401 Unauthorized. Forcing token refresh on next API call.")
                         self._access_token = None # Force re-auth
                         self._token_expires_at = datetime.now(timezone.utc) # Expire immediately
                         # Allow one more retry attempt immediately after this, as _get_headers will now re-auth
                         if retries < max_retries: retries +=1; continue
                 # For other non-429 HTTP errors or connection errors, usually not worth retrying
                 logging.error(f"Unrecoverable request error for {url}. Aborting request for this call.")
                 return None # Indicate failure
            except Exception as e: # Catch any other unexpected errors during request handling
                 logging.error(f"An unexpected error occurred making request to {url}: {e}", exc_info=True)
                 return None # Indicate failure

        logging.error(f"Request to {method} {url} failed after {max_retries} retries.")
        return None # Failed after all retries

    # --- Specific API Endpoint Methods ---

    def get_top_games(self, count=20):
        """Fetches the top games/categories."""
        logging.info(f"Fetching top {count} games/categories...")
        all_games = []
        params = {'first': min(count, 100)} # Max 100 per page
        cursor = None
        page_num = 0

        while len(all_games) < count:
             page_num += 1
             if cursor: params['after'] = cursor
             # logging.debug(f"Fetching games page {page_num} with params: {params}")

             response_data = self._make_request('GET', '/games/top', params=params)
             if not response_data or 'data' not in response_data:
                 logging.error(f"Failed to fetch top games (page {page_num}) or received invalid data.")
                 break

             games_batch = response_data['data']
             if not games_batch: # Empty data list means no more games
                # logging.info(f"No more games found on page {page_num}.")
                break
             all_games.extend(games_batch)
             # logging.info(f"Fetched batch of {len(games_batch)} games. Total so far: {len(all_games)}")

             cursor = response_data.get('pagination', {}).get('cursor')
             remaining_needed = count - len(all_games)
             if not cursor or remaining_needed <= 0: # No more pages or reached desired count
                 break

             params['first'] = min(100, remaining_needed) # Adjust for next request

        return all_games[:count] # Return only the requested number

    def get_streams_for_game(self, game_id, count=10):
        """Fetches top live streams for a specific game ID."""
        # logging.info(f"Fetching top {count} streams for game ID {game_id}...")
        params = {'game_id': game_id, 'first': min(count, 100)} # Max 100 per request
        response_data = self._make_request('GET', '/streams', params=params)

        if response_data and 'data' in response_data:
            # logging.info(f"Found {len(response_data['data'])} streams for game {game_id}.")
            return response_data['data']
        else:
            # Error details logged by _make_request
            # logging.warning(f"Failed to fetch streams for game {game_id} or no streams found.")
            return []

    def get_user_details(self, user_ids=None, user_logins=None):
        """Fetches details for specified users by ID or login (up to 100)."""
        if not user_ids and not user_logins:
            logging.warning("get_user_details called without user_ids or user_logins.")
            return []
        if (user_ids and len(user_ids) > 100) or \
           (user_logins and len(user_logins) > 100) or \
           (user_ids and user_logins): # API takes EITHER ids OR logins
             logging.error("get_user_details: Provide either up to 100 user_ids OR up to 100 user_logins, not both or more than 100.")
             return None # Indicate error

        params = {}
        identifier_type = ""
        if user_ids:
            params['id'] = user_ids
            identifier_type = f"IDs: {user_ids[:3]}..." if len(user_ids) > 3 else f"IDs: {user_ids}"
        elif user_logins:
            params['login'] = user_logins
            identifier_type = f"logins: {user_logins[:3]}..." if len(user_logins) > 3 else f"logins: {user_logins}"
        # logging.info(f"Fetching user details for {identifier_type}...")

        response_data = self._make_request('GET', '/users', params=params)

        if response_data and 'data' in response_data:
            # logging.info(f"Found details for {len(response_data['data'])} users.")
            return response_data['data']
        else:
            # Error details logged by _make_request
            # logging.error(f"Failed to fetch user details for {identifier_type}.")
            return None # Return None to indicate API failure or empty list if API returned empty data correctly

    def get_channel_videos(self, user_id, video_type='archive', limit=100, after_date=None):
        """Fetches videos for a channel, handling pagination and optional date cutoff."""
        # logging.info(f"Fetching up to {limit} '{video_type}' videos for user ID {user_id} published after {after_date.strftime('%Y-%m-%d') if after_date else 'any date'}...")
        all_videos = []
        params = {'user_id': user_id, 'first': min(limit, 100), 'type': video_type, 'sort': 'time'} # Most recent first
        cursor = None
        pages_fetched = 0
        # Max pages needed if all videos are kept; actual fetching might stop sooner due to date cutoff
        max_potential_pages = (limit + params['first'] -1) // params['first']


        while len(all_videos) < limit and pages_fetched < max_potential_pages:
            pages_fetched += 1
            if cursor: params['after'] = cursor
            # logging.debug(f"Fetching videos page {pages_fetched} for user {user_id} with params: {params}")

            response_data = self._make_request('GET', '/videos', params=params)
            if response_data is None : # API call failed completely
                # logging.error(f"API call failed fetching videos page {pages_fetched} for user {user_id}.")
                break
            if 'data' not in response_data: # Valid response but no 'data' key
                 logging.warning(f"Invalid response structure (missing 'data') fetching videos page {pages_fetched} for user {user_id}.")
                 break

            videos_batch = response_data['data']
            if not videos_batch: # Empty data list means no more videos of this type/sort
                # logging.info(f"No more '{video_type}' videos found on page {pages_fetched} for user {user_id}.")
                break

            # logging.info(f"Fetched batch of {len(videos_batch)} videos. Total before filter: {len(all_videos) + len(videos_batch)}. Checking against date cutoff...")

            stop_fetching_for_user = False
            for video in videos_batch:
                 # Filter by date AFTER fetching
                 if after_date:
                     published_at_str = video.get('published_at')
                     if published_at_str:
                         try:
                             published_at_dt = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                             if published_at_dt <= after_date: # Video is older than or same as cutoff
                                 # logging.info(f"Video {video.get('id')} ({published_at_dt.strftime('%Y-%m-%d')}) is not newer than cutoff {after_date.strftime('%Y-%m-%d')}. Stopping fetch for {user_id}.")
                                 stop_fetching_for_user = True
                                 break # Stop processing this batch further; subsequent videos will also be older
                         except ValueError:
                              logging.warning(f"Could not parse published_at '{published_at_str}' for video {video.get('id')} during date check.")
                     # else: logging.warning(f"Video {video.get('id')} missing published_at for date check.")


                 # Add video if not stopped by date and within the overall limit
                 if len(all_videos) < limit:
                     all_videos.append(video)
                 else:
                     # Reached the overall limit for this function call
                     # logging.info(f"Reached video fetch limit of {limit} for user {user_id}.")
                     stop_fetching_for_user = True
                     break # Stop processing this batch

            if stop_fetching_for_user:
                 break # Stop fetching more pages for this user

            # Prepare for next page
            cursor = response_data.get('pagination', {}).get('cursor')
            if not cursor: # No more pages available from API
                # logging.info(f"No pagination cursor found for user {user_id} after page {pages_fetched}. Assuming no more videos.")
                break

            params['first'] = min(100, limit - len(all_videos)) # Adjust 'first' for remaining needed
            if params['first'] <=0: break # Should be caught by len(all_videos) < limit

            time.sleep(0.1) # Small delay between paged requests for the same user

        # logging.info(f"Finished fetching '{video_type}' videos for user {user_id}. Collected {len(all_videos)} videos meeting criteria.")
        return all_videos

    def get_channel_follower_count(self, broadcaster_id):
        """
        Fetches the total follower count for a single broadcaster.
        """
        if not broadcaster_id:
            logging.warning("get_channel_follower_count called without broadcaster_id.")
            return None

        # This endpoint returns a paginated list, but also a 'total' field.
        # We only need the total, so we set 'first=1' to get a minimal response.
        params = {'broadcaster_id': broadcaster_id, 'first': 1}

        response_data = self._make_request('GET', '/channels/followers', params=params)

        if response_data and 'total' in response_data:
            return response_data['total']
        else:
            # This can happen for new channels or if the API call fails
            logging.warning(f"Could not retrieve follower count for broadcaster_id: {broadcaster_id}")
            return None # Return None to indicate failure or no data