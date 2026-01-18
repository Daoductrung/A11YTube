# A11YTube

Hello, I am **Đào Đức Trung**.

I developed **A11YTube** because I needed a tool that could keep up with my daily listening habits.

This project is built upon the excellent open-source foundation of **[Accessible Youtube Downloader Pro](https://github.com/sulaiman-alqusaimi/accessible_youtube_downloader_pro/)** by **Sulaiman Al Qusaimi**. I have always admired his work, but there were specific features I had long wished for—such as the ability to organize media into local collections, automatically find related videos, and skip silent parts in audio tracks.

With clear respect for the original software, I decided to extend it to include these capabilities and more, hoping to create a more personalized and efficient experience for blind users like myself.

## Key Capabilities

The application focuses on speed and efficiency, offering the following functions:

### Playback Enhancements
*   **Accessible Player**: Uses the VLC engine for reliable playback with standard keyboard controls.
*   **Silence Detection**: Analyzes audio to automatically skip silent intros or outros, helping to save time.
*   **Smart Suggestions**: Finds relevant related videos or mixes to play next when a track finishes.
*   **Resume Support**: Remembers the playback position of videos to continue listening later.

### Search and Organization
*   **Integrated Search**: Allows searching for videos directly within the application.
*   **Channel Downloads**: Supports downloading all videos from a specific channel URL found in search results.
*   **Library Management**:
    *   **Collections**: Manages custom local playlists and folders—a feature designed to bridge online and offline organization.
    *   **Favorites**: Saves preferred videos for quick access.
    *   **History**: Keeps a log of played items.

### Tools and Utilities
*   **Download Manager**: Options to download content as Video (MP4) or Audio (M4A/MP3).
*   **Clipboard Integration**: Detects YouTube links copied to the clipboard and offers immediate actions.
*   **Screen Reader Support**: Provides direct speech feedback optimized for NVDA.

## Technology Stack

The application relies on standard open-source libraries:
*   **Python 3**: The core language.
*   **wxPython**: For the user interface.
*   **VLC Media Player (libvlc)**: For playback.
*   **yt-dlp**: For media extraction.
*   **FFmpeg**: For audio processing.
*   **NVDA Controller Client**: For speech feedback.

## Installation

An installer (`A11YTube_Setup.exe`) is available on the releases page which handles all dependencies automatically.

For developers running from source:
1.  Install **Python 3.x**.
2.  Install libraries: `pip install -r requirements.txt`
3.  Ensure `ffmpeg.exe`, `ffprobe.exe`, and `libvlc` are available.
4.  Run `python source/A11YTube.py`.

## Acknowledgements

I am deeply grateful to:

*   **Sulaiman Al Qusaimi**: For making his project, **Accessible Youtube Downloader Pro**, open source. It served as the essential base for this application.
*   **Antigravity (Google DeepMind)**: For the extensive assistance in architectural design, code optimization, and technical support throughout the development process.
*   The open-source community for maintaining the libraries that make this software possible.
