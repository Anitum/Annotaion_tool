# Annotation Tool

A tool for annotating images.

## Features

*   **Video and Frame Navigation:** Browse through videos and their frames.
*   **Bounding Box Annotation:** Draw, modify, and delete bounding boxes on images.
*   **Class Management:** Assign classes to bounding boxes from a configurable list.
*   **Configuration:** Customize settings like maximum frames per video, sampling strategy, class names, and colors via a `config.json` file.
*   **Data Persistence:** Annotations are saved in the `annotations` directory.
*   **Web Interface:** Access the tool through a web browser.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python app.py
   ```
2. Open your web browser and navigate to `http://localhost:5000`.

## Project Structure

*   `app.py`: The main Flask application file.
*   `requirements.txt`: Python dependencies.
*   `README.md`: This file.
*   `config.json`: Configuration file for classes, colors, and sampling.
*   `templates/`: HTML templates for the web interface.
*   `annotations/`: Directory where annotation files are stored.
*   `class_images/`: Directory for storing sample images for classes (if used).
*   `nohup.out`: Log file (likely from running the server in the background).
*   `Working_Backup_app.py`: A backup file (consider removing or adding to .gitignore).

## Configuration

The tool uses a `config.json` file to manage settings. Key configurable options include:

*   `max_frames_per_video`: Maximum number of frames to load per video.
*   `sampling_strategy`: Method to sample frames (e.g., "first", "uniform", "random").
*   `classes`: A dictionary mapping class IDs to names (e.g., `{"0": "Person", "1": "Vehicle"}`).
*   `class_colors`: A dictionary mapping class IDs to RGB color arrays for bounding boxes.

Default values are provided if `config.json` is missing or incomplete.
