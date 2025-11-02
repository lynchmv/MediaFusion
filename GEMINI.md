# Project Overview

MediaFusion is a powerful Stremio and Kodi add-on designed for media streaming. It provides extensive catalogs across multiple languages and offers enhanced streaming capabilities by integrating with various torrent and cloud storage services. The project features advanced scrapers for diverse content, including specialized support for sports, regional content, and integration with tools like Prowlarr and Jackett.

**Key Technologies:**

*   **Backend:** Python (FastAPI), MongoDB (using Beanie ODM), Redis, Dramatiq (for asynchronous tasks), Scrapy (for web scraping).
*   **Deployment:** Docker, Docker Compose, Kubernetes.
*   **Frontend (Configuration UI):** Jinja2 templating.
*   **Dependency Management:** `uv`.

**Core Features:**

*   **Rich Catalogs:** Comprehensive content libraries in multiple languages (Tamil, Hindi, Malayalam, Kannada, English) and dubbed movies, series, and live TV.
*   **Diverse Streaming Providers:** Supports direct torrents, and various cloud/debrid services like PikPak, Seedr.cc, OffCloud, Torbox, Real-Debrid, Debrid-Link, Premiumize, AllDebrid, qBittorrent (WebDav), and StremThru.
*   **Advanced Scraper Support:** Specialized scrapers for Formula Racing, Fighting Sports (UFC, WWE), American sports, live events (DaddyLiveHD), regional content (TamilMV, TamilBlasters, TamilUltra, NowMeTV), Prowlarr integration, Torrentio/KnightCrawler streams, Zilean DMM search, and MPD DRM scraping.
*   **Security & Privacy:** API security with optional password protection, user data encryption, and DMCA take-down support.
*   **User Experience Enhancements:** Watchlist catalog synchronization, customizable stream filters (file size, resolution, seeders), poster display with titles, M3U playlist import, manual scraper triggering UI, and parental controls.
*   **Integrations:** IMDb ratings display, RPDB posters, browser download support, manual torrent contribution, and Jackett indexer support.

# Building and Running

This project utilizes `uv` for dependency management and `Docker` for containerization, making it highly portable.

## Local Development with Docker Compose

The recommended way to run MediaFusion locally is using Docker Compose, which sets up all necessary services (MediaFusion API, Nginx, MongoDB, Redis, Dramatiq worker, Prowlarr, Flaresolverr, Browserless, and monitoring tools).

1.  **Prerequisites:** Ensure Docker and Docker Compose are installed on your system.
2.  **Environment Configuration:** Create a `.env` file in the `deployment/docker-compose/` directory based on `.env-sample` and configure your settings.
3.  **Build and Run:**
    ```bash
    cd deployment/docker-compose
    docker-compose up --build -d
    ```
    This command will build the `mediafusion` Docker image and start all services in detached mode.

## Manual Installation (Python)

While Docker is preferred, you can also run the application directly using Python.

1.  **Install `uv`:**
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
2.  **Install Dependencies:**
    ```bash
    uv sync
    ```
3.  **Run the API (using Uvicorn):**
    ```bash
    uvicorn api.main:app --host 0.0.0.0 --port 8000
    ```
    For production, consider using `gunicorn` with `uvicorn` workers as indicated in `Procfile`:
    ```bash
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app -b 0.0.0.0:$PORT
    ```

## Kodi Add-on

Refer to the `README.md` for detailed installation instructions for the Kodi add-on, including repository and manual installation methods.

## Makefile Commands

The `Makefile` provides several useful commands for development and deployment:

*   `make build`: Builds the Docker image for the application.
*   `make build-multi`: Builds multi-platform Docker images.
*   `make push`: Pushes the Docker image to the configured repository.
*   `make update-version VERSION_NEW=<version>`: Updates the project version across various configuration files.
*   `make prompt VERSION_OLD=<old_version> VERSION_NEW=<new_version>`: Generates release notes based on Git commit history.
*   `make generate-notes`: Generates release notes using Claude AI (requires `ANTHROPIC_API_KEY`).
*   `make generate-reddit-post`: Generates a Reddit post about the update using Claude AI (requires `ANTHROPIC_API_KEY`).

# Development Conventions

*   **Code Style:** Python-based, likely adhering to common Python style guides (e.g., Black, Flake8), though not explicitly defined in the provided files.
*   **API Framework:** FastAPI is used for building the web API.
*   **Database:** MongoDB is the primary database, accessed via the Beanie ODM.
*   **Asynchronous Tasks:** Dramatiq is used for handling background tasks.
*   **Web Scraping:** Scrapy is employed for advanced web scraping functionalities, with `mediafusion_scrapy/settings.py` configuring its behavior.
*   **Configuration:** Project settings are managed through `db/config.py` and environment variables.
*   **Testing:** While specific test commands are not detailed, the project structure implies a focus on robust functionality given the complexity of scraping and streaming integrations.
