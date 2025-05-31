[阅读中文版 (Read this document in Chinese)](README.md)

# SimaiCut - Simai Chart and Audio Clipper

SimaiCut is a Python toolkit designed to help users process, clip, and concatenate [Simai](https://www.piugame.com/data/simai_format.html) format music game charts and their corresponding audio files. It allows for easy extraction of segments from existing charts, speed adjustments, and combining multiple segments into new charts and audio.

## Key Features

* **Synchronized Chart & Audio Processing**: Performs unified clipping and transformation operations on both chart files (`maidata.txt`) and audio files (`track.mp3`).
* **Segment Cropping**: Accurately crops charts and audio for specified time durations.
* **Speed Adjustment**: Synchronously accelerates or decelerates chart events and audio playback.
* **Multi-Segment Concatenation**:
    * Sequentially concatenates multiple (cropped) chart and audio segments.
    * Automatically calculates and inserts silent audio gaps of configurable duration between segments.
    * At the chart level, fills these gaps with an appropriate number of placeholder notes and comma events, timed according to the BPM at the end of the preceding song.
    * Supports adding fade-in/fade-out effects at audio concatenation points.

## Getting Started

### Prerequisites

* **Python 3.7+**
* **FFmpeg**: Must be installed and its executable path added to the system's `PATH` environment variable. FFmpeg is used for all audio processing operations.
* **[SimaiParser](https://github.com/Choimoe/PySimaiParser)**: This project relies on the `SimaiParser` library to parse and reconstruct Simai chart data. Ensure this library is correctly installed or available in the project's Python path:
  ```bash
  pip install PySimaiParser
  ```

### Project Structure

```
SimaiCut/
├── SimaiCut/
│   ├── init.py
│   ├── audio.py              # Audio processing module
│   ├── chart.py              # Chart editing logic (crop, accelerate, concatenate)
│   ├── editor.py             # Simai chart editor class (wraps SimaiParser)
│   ├── processor.py          # Core processor class, coordinates audio and chart operations
│   └── util.py               # Utility functions (BPM calculation, time snapping, etc.)
├── README.md                 # This document (Chinese)
└── README_en.md              # English version of this document
```

## Module Overview

* **`processor.SongProcessor`**:
    The core class that encapsulates loading, processing (cropping, accelerating), and concatenating operations for a single song (audio + chart) with other `SongProcessor` instances. It manages temporary audio and chart files.
* **`editor.SimaiEditor`**:
    Wraps `SimaiParser` to provide a higher-level interface for chart editing. It converts Simai text charts into an internal JSON structure for manipulation and can convert the modified structure back to Simai text.
    * `crop()`: Crops the chart.
    * `accelerate()`: Accelerates the chart.
    * `concatenate()`: Appends another chart to the current one, handling the gap.
* **`audio.AudioProcessor`**:
    Contains a series of static methods that use FFmpeg to perform audio operations, such as getting duration, cropping, accelerating, applying fades, creating silence, and concatenating lists of audio files.
* **`chart.py`**:
    Contains the actual chart manipulation logic (implementation details for crop, accelerate, concatenate) for the `SimaiEditor` class. These methods are dynamically assigned to the `SimaiEditor` class.
* **`util.py`**:
    Provides general utility functions, such as getting the BPM at a specific time in a chart and snapping time points to a musical grid.

## Contributing

Pull Requests and Issues are welcome to improve this project!
