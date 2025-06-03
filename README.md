# Title Plotter - Philippine Land Titles

A QGIS plugin for plotting land parcels from Philippine land titles using bearing-distance data. This tool helps non-surveyors and professionals plot lots using tie points, requiring no GIS background.

## Features

- Plot land parcels from bearing-distance data
- Built-in database of Philippine tie points
- Real-time preview of parcel geometry
- Optional OCR for digitizing technical descriptions
- Support for PRS92 and WGS84 coordinate systems

## Installation

1. Download from QGIS Plugin Repository or clone this repository
2. Extract to your QGIS plugins directory:
   - Windows: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Enable in QGIS: Plugins > Manage and Install Plugins

## Basic Usage

1. Click "Title Plotter" icon in QGIS toolbar
2. Select a tie point from the database
3. Enter bearing and distance data
4. Preview and plot the parcel

## OCR Support (Optional)

For OCR functionality:
1. Install Tesseract OCR
2. Install Python packages:
   ```bash
   pip install pytesseract Pillow opencv-python
   ```

## Requirements

- QGIS 3.22 or later
- Python 3.x
- Required packages: pandas, shapely
- Optional packages: pytesseract, Pillow, opencv-python (for OCR)

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

## Author

Isaac Melchor Velasquez Enage (isaacenagework@gmail.com)

## Acknowledgments

- QGIS Plugin Builder
- Philippine Geodetic Engineers
- Open Source Community
