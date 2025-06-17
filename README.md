# Twitch Insight: Data Collector & Collaboration Network Analyzer

## 🚀 Introduction

Twitch Insight is a Python-based project designed to collect data from the Twitch API, store it in a local SQLite database, and perform analysis, with a special focus on understanding collaboration networks between streamers. It identifies potential collaborations by detecting `@mentions` in video titles and descriptions, and also explores community structures within these networks. The primary interface for data collection, processing, and exploration is a Jupyter Notebook.

## ✨ Features

* **Automated Data Collection:**
    * Fetches top categories (games) and top live streams within those categories.
    * Retrieves detailed information for Twitch channels (profile, follower counts, etc.).
    * Archives video metadata (VODs, highlights) for collected channels, including game/category context.
* **Collaboration Network Analysis:**
    * Detects potential collaborations by parsing `@mentions` in video titles and descriptions.
    * Constructs a collaboration graph where channels are nodes and mentions create weighted edges (based on frequency, duration, and recency of collabs).
    * Stores collaboration data, including the game/category context of each interaction.
    * Discovers new channels through mentions and integrates them into the data collection process.
* **Community Detection:**
    * Applies the Louvain algorithm to the collaboration graph to identify communities of densely connected streamers.
* **Data Persistence:**
    * Stores all collected data in a local SQLite database (`twitch_data.db`), allowing for resumable operations and long-term data accumulation.
* **Resumable & Maintainable:**
    * Designed to be stopped and restarted, continuing from where it left off (e.g., processing unprocessed videos for mentions, refreshing channel data).
    * Includes a refresh cycle to update information for a random subset of channels.
* **Interactive Exploration:**
    * Jupyter Notebook interface for running collection cycles and exploring data.
    * Basic statistics and visualizations for collected channels, videos, and categories.
    * Interactive search and visualization of a channel's immediate collaboration network snippet.
    * Configurable filters for network analysis to manage performance with large datasets.
* **Configurable:**
    * Key parameters (API limits, batch sizes, refresh rates, network analysis thresholds) are managed in a `config.py` file.

## 📁 Project Structure

The project is organized into several Python modules and a main Jupyter Notebook:

* **`.env` (Create this file manually)**: Stores your sensitive Twitch API Client ID and Client Secret.
* **`requirements.txt`**: Lists all Python dependencies for easy installation.
* **`config.py`**: Defines all configuration parameters, constants, and API endpoints. Reads credentials from `.env`. Prints current settings when the notebook starts.
* **`database.py`**: Manages all interactions with the SQLite database, including schema initialization, data insertion, updates, and querying. Ensures atomic operations for critical updates.
* **`twitch_api.py`**: A client class for interacting with the Twitch Helix API. Handles authentication, rate limiting, pagination, and data fetching for various endpoints (games, streams, users, videos).
* **`network_utils.py`**: Utility functions for network-related tasks, primarily extracting `@mentions` from text and validating them against the database.
* **`twitch_data_collector.ipynb`**: The main Jupyter Notebook that orchestrates the entire process.
* **`twitch_data.db` (Generated)**: The SQLite database file where all data is stored.

## 🏁 Getting Started

### 1. Prerequisites

* Python 3.7+
* `pip` (Python package installer)
* Jupyter Notebook or JupyterLab

### 2. Clone the Repository (if applicable)

If this project is hosted on a Git repository (e.g., GitHub):
```bash
git clone <repository_url>
cd <repository_directory>
```

Otherwise, ensure all the .py files, requirements.txt, and the .ipynb file are in the same directory.

### 3. Set Up Twitch API Credentials

* Go to the Twitch Developer Console and register a new application to get a Client ID and Client Secret. Choose "Server-to-Server" type for an App Access Token.
* In the project's root directory, create a file named `.env`.
* Add your credentials to the .env file in the following format:

```
TWITCH_CLIENT_ID="your_client_id_here"
TWITCH_CLIENT_SECRET="your_client_secret_here"
```

### 4. Install Dependencies

It's highly recommended to use a Python virtual environment to manage your project's dependencies.

* Create and Activate a Virtual Environment (Optional but Recommended): Open your terminal or command prompt, navigate to your project's root directory, and run:

```bash
# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS and Linux:
source venv/bin/activate
```

* Install Dependencies using requirements.txt: Once your virtual environment is activated (or if you choose not to use one), install all the required Python libraries using the provided requirements.txt file:

```bash
pip install -r requirements.txt
```

This file includes all necessary packages such as requests, python-dotenv, pandas, matplotlib, seaborn, notebook, jupyterlab, networkx, python-louvain, and ipywidgets.

### 5. Enable Jupyter Widgets Extension (if needed)

For interactive widgets (like dropdowns and search boxes) to work correctly in Jupyter Notebook or JupyterLab, you might need to enable the ipywidgets extension.

* For Jupyter Notebook:
```bash
jupyter nbextension enable --py widgetsnbextension --sys-prefix
```

* For JupyterLab:
```bash
jupyter labextension install @jupyter-widgets/jupyterlab-manager
```

You might need Node.js installed for JupyterLab extensions. Restart JupyterLab after installation.

### 6. Configure Parameters (Optional)

Review and adjust parameters in config.py to suit your needs (e.g., number of items to fetch, refresh rates, network analysis thresholds). The defaults are set to be relatively conservative.

## 🚀 Usage Instructions

1. **Start Jupyter:**
   Navigate to the project directory in your terminal and launch Jupyter Notebook or JupyterLab:
   ```bash
   jupyter notebook
   # OR
   jupyter lab
   ```

2. **Open the Notebook:**
   Open the `twitch_data_collector.ipynb` file in Jupyter.

3. **Run Cells Sequentially:**
   Execute the cells in the notebook one by one.
   * Cell 1 (Setup): Imports libraries, loads and prints configuration, initializes the database connection, and sets up the Twitch API client.
   * Cell 2 (Data Collection Cycle Function & Execution): Defines and runs run_collection_cycle. This function fetches top streams/categories and then details/videos for channels found.
   * Cell 3 (Mention Processing Function): Defines process_video_mentions_batch. This is the core logic for finding mentions in videos, looking up unknown channels, and atomically updating collaboration data (including game context).
   * Cell 4 (Mention Processing Loop): Executes process_video_mentions_batch in a loop for a configured number of batches. This cell processes videos already in the database whose mentions haven't been checked yet. This cell can take a long time if there are many unprocessed videos.
   * Cell 5 (Refresh Function): Defines run_refresh_cycle to update details and fetch new videos for a random subset of channels.
   * Cell 6 (Run Refresh Cycle): Executes the refresh cycle.
   * Subsequent Cells (Data Exploration & Network Analysis): These cells load data from the database into pandas DataFrames and provide:
     * Basic statistics and visualizations for channels, videos, and categories.
     * Loading and in-memory filtering of collaboration data for network analysis based on thresholds in config.py.
     * Statistics and visualizations for the filtered collaboration network (e.g., degree distribution).
     * Community detection using the Louvain algorithm on the filtered graph and visualization of communities on a subgraph.
     * An interactive section to search for any channel (from the full dataset) and visualize its immediate collaboration network snippet.

**Important Notes:**

* **Initial Run:** On the first run, the database will be created. Some data collection cycles (especially mention processing) might take a significant amount of time depending on the configured parameters and API responsiveness. The script includes print statements with progress and basic time estimations.
* **Interrupting and Resuming:** The notebook can be interrupted using Jupyter's "Interrupt Kernel" functionality (the stop button). The processing loops are designed to be resumable. Data already saved to the database will persist.
* **API Rate Limits:** The twitch_api.py client includes rate limit handling. However, aggressive fetching parameters in config.py could still lead to extended wait times.
* **Incremental Video Fetching:** The script is designed to build your video archive incrementally. Each data collection or refresh cycle only fetches a limited number of the most recent videos for a channel (e.g., 50 or 100, as set in the notebook code). This is an intentional design to keep individual runs fast and manage API usage. Over multiple runs, the database will accumulate a more complete history for each channel as it repeatedly fetches the newest content since the last check.

## ⚙️ Configuration (config.py)

The config.py file is central to controlling the script's behavior:

* **Data Collection Parameters:** Control how many categories, streams, etc., are fetched in each primary collection cycle, and how often channel details/videos are refreshed.
* **Mention Processing Parameters:** Control the batch size and max batches for the dedicated mention processing loop.
* **Refresh Cycle Parameters:** Control how many random channels are picked for a full refresh in the dedicated refresh cycle.
* **Network Analysis Thresholds:** Define minimums (e.g., collaboration count, channel view count, video count) for filtering data in memory before performing network analysis and visualizations. This helps manage performance with large datasets without deleting data from the database.

The current configuration values are printed when you run the first cell of the notebook.

## 🗃️ Database (twitch_data.db)

All collected data is stored in an SQLite database named twitch_data.db (or as configured). Key tables include:

* **Categories:** Stores Twitch game categories (ID, name).
* **Channels:** Stores detailed information about Twitch channels (ID, login, display name, description, view count, profile image URL, etc.).
* **Videos:** Stores metadata for channel videos/VODs (ID, channel ID, title, publication date, duration, view count, game context, mentions_processed_at timestamp).
* **Collaborations:** Stores summarized collaboration edges between pairs of channels (channel IDs, total collaboration count, total duration, latest/first collab timestamp).
* **CollaborationContext:** Stores the context of collaborations, specifically breaking down collaboration counts and durations by the game/category under which the interaction (mention in video) occurred.

## ⚠️ Limitations & Potential Future Work

* **Focus on Recent Videos:** The data collection process is optimized to fetch a limited number of the *most recent* videos (e.g., the latest 50-100) from a channel during each cycle. This intentional design keeps the collection runs fast and manageable while prioritizing current data. While a channel's video history is built up incrementally over many runs, the script is not designed to download a channel's entire video catalog in one go.
* **"Streaming Together" Feature:** The Twitch API (as of June 2025) does not seem to provide a straightforward way to get participant data from the "Streaming Together" / "Squad Stream" / "Guest Star" features for *archived* videos. Collaboration detection currently relies on `@mentions`.
* **Follower Counts:** The script fetches follower counts, which is a great improvement over the deprecated `view_count`. However, this requires an additional API call per channel during detail fetches, making those steps slower.
* **Time Estimations:** While basic time estimations are provided for some loops, they can be inaccurate due to API response variability, rate limit delays, and the changing nature of the data being processed.
* **Scalability for Extremely Large Networks:** For truly massive networks (millions of nodes/edges), pandas and NetworkX in-memory processing might become a bottleneck. Database-level graph processing or specialized graph databases could be considered for such scales.
* **Advanced Community Analysis:** Could extend to track community evolution over time, analyze inter-community interactions, or use different community detection algorithms.
* **UI/Dashboard:** A web-based UI (e.g., using Dash or Streamlit) could provide a more user-friendly way to explore the collected data and network.
* **Error Granularity in API Client:** The `twitch_api.py` client currently returns `None` on some unrecoverable API errors. More specific error types or status codes could be propagated to the caller for finer-grained error handling in the notebook.