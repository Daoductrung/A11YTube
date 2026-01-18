# A11YTube

Hello, I am **Đào Đức Trung**. I built **A11YTube** with a simple goal: to make the vast world of YouTube content truly accessible and efficient for blind users like myself. While there are many media players out there, I wanted a tool that prioritized speed, simplicity, and keyboard efficiency above all else.

## The Philosophy

My design philosophy for A11YTube is "Content First". I wanted to strip away the visual clutter and complex navigation of standard web interfaces. Instead, I focused on creating a streamlined environment where finding and enjoying media happens almost instantly.

## Key Capabilities

I have engineered this application to handle the complete media workflow—from discovery to playback and preservation—while keeping the interface clean and responsive.

### 1. Seamless Playback Experience
At the heart of the application is a robust media player powered by the reliable **VLC** engine. I wanted the listening experience to be fluid, so I implemented:
*   **Smart Silence Detection**: Using **FFmpeg**, the application can analyze audio in real-time to detect and skip silent intros or outros. This saves valuable time when listening to music playlists.
*   **Adaptive Modes**: You can switch between Video mode for full content or Audio-only mode to save bandwidth and system resources.
*   **Resume Capability**: The application remembers exactly where you left off, so you can close it and return to your podcast or audiobook later without losing your place.

### 2. Intelligent Discovery
Finding new content should be effortless.
*   **Integrated Search**: I built a search system directly into the app, allowing you to browse results without ever opening a web browser.
*   **Continuous Play**: I designed an algorithm that automatically finds related videos or "Mixes" when your current track ends, ensuring the audio never stops unexpectedly.
*   **Channel Access**: You can easily retrieve and download all videos from a specific channel directly from the search results.

### 3. Personal Library Management
I believe users should own their organization. A11YTube offers several ways to manage your content locally:
*   **Collections**: This is a flexible system allowing you to create your own folders and playlists. You can even merge online playlists into your local collections for offline organization.
*   **Favorites & History**: Simple, accessible lists keep track of what you love and what you have recently played.

### 4. Powerful Downloading
For those times when you need offline access, I included a comprehensive download manager provided by **yt-dlp**. It supports downloading single tracks, full playlists, or entire channels in various formats like MP4 or high-quality MP3/M4A.

### 5. Accessibility Integration
Since this tool is for us, I ensured deep integration with screen readers.
*   **Direct Speech**: The app communicates directly with **NVDA**, confirming important actions like "Downloading" or "Buffering" instantly.
*   **Clipboard Monitoring**: It quietly watches your clipboard; copy a YouTube link anywhere, and A11YTube will offer to play or download it immediately.

## Technology Stack

This project stands on the shoulders of open-source giants. I utilized **Python 3** and **wxPython** for the foundation, **VLC** for playback, **yt-dlp** for media extraction, and **FFmpeg** for audio processing.

## Installation

I have packaged the application into a simple installer (`A11YTube_Setup.exe`) available on the releases page. It handles all the complex dependencies for you, so you can just install and run.

If you are a developer and wish to run from source, you will need Python 3 and the requirements listed in the repository.

## Acknowledgements

I am deeply grateful to those who paved the way:
*   **Sulaiman Al Qusaimi**, whose "Accessible Youtube Downloader Pro" was the original spark that inspired me to start this project.
*   **Antigravity (Google DeepMind)**, for the invaluable assistance in architectural design, code optimization, and helping me bring this vision to life.
*   The open-source community for maintaining the essential libraries that make this software possible.
