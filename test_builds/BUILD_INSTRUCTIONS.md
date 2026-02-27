# A11YTube Android APK Build Instructions

This document explains why the APK file could not be generated within this sandbox environment and how to build it locally.

## Build Failure Reason

The sandbox environment lacks the necessary `flet` command-line tool and the Android SDK/NDK infrastructure required to compile Python/Flet code into an Android APK.

## Build Instructions

To build the APK for testing, follow these steps on a machine with Python, Flet, and Android SDK installed (or use GitHub Actions):

1.  **Install Flet:**
    ```bash
    pip install flet
    ```

2.  **Navigate to the Android Project Directory:**
    ```bash
    cd android_version
    ```

3.  **Run the Build Command:**
    ```bash
    flet build apk
    ```
    *Note: This might require installing the `flutter` SDK as well, depending on your setup.*

4.  **Locate the APK:**
    The output APK will be in the `build/apk` directory (or wherever `flet build` outputs by default).

## Project Structure for Build

The project is located in `android_version/` and contains:
*   `main.py`: The entry point.
*   `core/`: Core logic (database, downloader, settings).
*   `assets/`: (Empty placeholder for icons/images).
*   `requirements.txt`: Python dependencies.

## Testing

Once built, transfer the APK to your Android device and install it. Ensure TalkBack is enabled to verify accessibility features.
