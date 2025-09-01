# Twitch Insight: Data Collector & Collaboration Network Analyzer

## 🚀 Introduction

Twitch Insight is a comprehensive Python framework designed to collect data from the Twitch API, store it in a local SQLite database, and perform advanced social network analysis. It moves beyond simple statistics to map the implicit collaboration network between streamers.

The system identifies collaborations by parsing `@mentions` in video titles, validates each mention to ensure data integrity, and stores every interaction in a granular database. It uses BERTopic for state-of-the-art topic modeling to derive data-driven context for *why* streamers collaborate. The entire project is orchestrated through a powerful Jupyter Notebook that functions as both a control panel for automated data collection and an interactive canvas for data exploration and analysis.

## ✨ Features

* **Automated & Resumable Data Collection:**
    * **Intelligent Cycles:** An automated main loop prioritizes processing existing data (mentions) before refreshing stale channels, and then discovering new ones via top streams.
    * **Resilient by Design:** All collection processes are interruptible and resumable. Atomic database operations prevent data corruption.
    * **Efficient Fetching:** API calls are batched where possible to maximize speed and respect rate limits. The refresh cycle intelligently prioritizes the "stalest" channels.
* **Granular Collaboration Tracking:**
    * **Mention-Based Detection:** Detects collaborations by parsing `@mentions` in video titles.
    * **API Validation:** Every potential mention is validated against the Twitch API to filter out typos and inactive channels, ensuring high data quality.
    * **Detailed Logging:** Each collaboration instance is logged in a `Mentions` table, linking the source channel, target channel, and the specific video it occurred in.
* **Advanced Network Analysis:**
    * **Graph Construction:** Builds a weighted, undirected graph of streamer collaborations from the collected data.
    * **Centrality Analysis:** Identifies influential "hub" and "bridge" channels using PageRank.
    * **Community Detection:** Uses the Louvain method to discover densely connected clusters of streamers within the network.
* **Data-Driven Context with Topic Modeling:**
    * **BERTopic Integration:** Employs BERTopic to analyze video titles and discover emergent topics (e.g., specific games, content types like "Vlogs").
    * **Outlier Reduction:** Includes an optional step to intelligently re-assign outlier videos to the most relevant topic, increasing contextual coverage.
* **Rich & Interactive Visualization:**
    * **Statistical Plots:** Generates plots for channel/video statistics and network properties like degree distribution.
    * **Clustered Community Graph:** Visualizes the network with nodes colored by their community and positioned in visual clusters, with labels derived from characteristic channel tags.
    * **Interactive Network Snippet:** A powerful searchable widget to generate a local network graph for any channel, with selectable degrees of separation.
    * **Image Nodes:** An optional toggle allows you to render nodes as channel profile pictures with colored community borders for a more immersive view.

## 📁 Project Structure

* **`.env` (Manual Creation Required)**: Stores your sensitive Twitch API credentials.
* **`requirements.txt`**: Lists all Python dependencies for easy one-command installation.
* **`config.py`**: Centralizes all user-configurable parameters (e.g., collection limits, analysis thresholds) and prints the current settings when the notebook starts.
* **`database.py`**: Manages all SQLite database interactions, including schema creation and atomic data operations.
* **`twitch_api.py`**: The client for all interactions with the Twitch Helix API, featuring built-in rate-limit handling.
* **`network_utils.py`**: Helper functions for text processing and mention extraction.
* **`twitch_data_collector.ipynb`**: The main Jupyter Notebook that orchestrates all data collection, processing, analysis, and visualization.
* **`twitch_data.db` (Generated)**: The SQLite database file where all data is stored.
* **`image_cache/` (Generated)**: A directory created to cache downloaded channel profile pictures, speeding up repeated visualizations.

## 🏁 Getting Started (Google Colab)

You can run the entire notebook in Google Colab without any local setup. Just follow these steps:
1. **Open the Notebook in Colab:** Click [this link](https://colab.research.google.com/github/J-morag/TwitchSocialNetwork/blob/master/twitch_data_collector.ipynb) to open the notebook directly in Google Colab.
2. **Optional - Set Up Twitch API Credentials:** Create a `.env` file in the Colab environment with your Twitch API credentials. The formats are the same as described in the local setup section below.
3. **Setup & Install Dependencies:** The first two code cells in the notebook handle all necessary installations and setup. After running the second cell, you must restart the Colab runtime.
4. **Run the Cells Sequentially:** Execute the cells in order.
5. Note that some interactive widgets may have limited functionality in Colab compared to a local Jupyter environment.
6. It is recommended to run using a GPU backend, since training the BERTopic model will be significantly faster.

## 🏁 Getting Started (local setup)

### 1. Prerequisites

* Python 3.7+
* `pip` (Python package installer)
* Jupyter Notebook or JupyterLab

### 2. Set Up Twitch API Credentials

* Go to the [Twitch Developer Console](https://dev.twitch.tv/console/) and **Register Your Application** to get a **Client ID** and **Client Secret**.
* Choose **Confidential** for the Client Type. For the "OAuth Redirect URL", you can use `http://localhost`.
* In your project's root directory, create a file named `.env`.
* Add your credentials to it:
    ```env
    TWITCH_CLIENT_ID="your_client_id_here"
    TWITCH_CLIENT_SECRET="your_client_secret_here"
    ```

### 3. Install Dependencies & Fonts

It's highly recommended to use a Python virtual environment.

* **Install Python Packages:**
    Open your terminal in the project directory and run:
    ```bash
    pip install -r requirements.txt
    ```
* **Install a CJK Font (Recommended for Visualization):** To prevent errors when displaying international channel tags, it is recommended to install a font with broad Unicode support.
    * **Recommended Font:** [Google Noto CJK](https://fonts.google.com/noto/specimen/Noto+Sans+JP)
    * **On Linux (Debian/Ubuntu):** `sudo apt-get install fonts-noto-cjk`
    * **On Windows/macOS:** Download and install the font family manually.
    * After installing, you may need to clear your matplotlib font cache (see instructions in the notebook).

### 4. Enable Jupyter Widgets Extension

For the interactive visualization widgets to work, enable the extension:

* **For Jupyter Notebook:**
    ```bash
    jupyter nbextension enable --py widgetsnbextension --sys-prefix
    ```
* **For JupyterLab:**
    ```bash
    jupyter labextension install @jupyter-widgets/jupyterlab-manager
    ```

## 🚀 Usage Instructions

1.  **Launch Jupyter:** Open your terminal in the project directory and run `jupyter notebook` or `jupyter lab`.
2.  **Open the Notebook:** Open the `twitch_data_collector.ipynb` file.
3.  **Run Cells Sequentially:** Execute the cells in order. The notebook is divided into logical sections:
    * **Setup:** Initializes all components and prints the current configuration.
    * **Data Collection Cycles:** You can run these cells manually to perform specific tasks (fetch top streams, process mentions, refresh data).
    * **Automated Main Loop:** This is the recommended "run and walk away" cell that intelligently runs the collection cycles until the database is stable.
    * **Data Exploration:** Cells that load the collected data and display basic statistics and plots.
    * **Network Analysis & Visualization:** A series of cells that filter the data, perform centrality and community analysis, and generate visualizations of the collaboration network.
    * **Interactive Snippet:** The final section provides the searchable widget to explore any channel's local network on demand.

## ⚠️ Limitations & Potential Future Work

* **Collaboration Signals:** The model relies on `@mentions`. It cannot detect verbal shout-outs or collaborations via Twitch's "Guest Star" feature (as this is not exposed in the VOD API).
* **Focus on Recent Videos:** The collection process is intentionally optimized to fetch a limited number of recent videos per channel in each cycle. A channel's complete historical archive is built gradually over many runs.
* **Time Estimations:** The ETA printouts are heuristic and can be inaccurate due to API variability and rate limit delays.
* **Scalability:** For extremely large networks (millions of nodes/edges), pandas and NetworkX in-memory processing may become a bottleneck. Future work could explore graph databases.
* **Future Work:**
    * **Temporal Network Analysis:** Study how the network structure and community affiliations evolve over time.
    * **Directed Graph Analysis:** Analyze the network as a directed graph to study reciprocity and influence flow.
    * **Dashboard Development:** Create an interactive web-based dashboard (e.g., using Dash or Streamlit) for easier exploration.

## ⚠️ Aknowledgement of the Use of Large Language Models
* **LLM Code:** Most of the code in this project was designed and written by Google Gemini 2.5 Pro.
