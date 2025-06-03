# Title Plotter - Philippine Land Titles

A QGIS plugin designed to automate the plotting of land parcels using the official Philippine land title format. Built specifically for geodetic engineers, GIS analysts, and real estate professionals, this tool allows users to input technical descriptions (bearing-distance or metes-and-bounds format) and instantly generate accurate parcel geometries.

## Features

- **Intelligent Bearing Parsing**: Automatically interprets common Philippine survey notations from TCTs and OCTs
- **Coordinate System Support**: Works with both PRS92 and WGS84 coordinate systems
- **Tie Point Selection**: Built-in database of common tie points for accurate parcel positioning
- **Real-time Preview**: Visual feedback of parcel geometry as you input data
- **OCR Support**: Optional OCR functionality for digitizing technical descriptions from scanned TCTs
- **Input Validation**: Ensures accurate data entry with real-time validation
- **WKT Generation**: Exports parcel geometry in Well-Known Text format

## Installation

1. Download the plugin from the QGIS Plugin Repository or clone this repository
2. Extract the files to your QGIS plugins directory:
   - Windows: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Enable the plugin in QGIS through Plugins > Manage and Install Plugins

## Usage

1. **Start the Plugin**: Click the "Title Plotter" icon in the QGIS toolbar
2. **Select Tie Point**: Use the tie point selector to choose a reference point
3. **Enter Technical Description**: Input bearing and distance data
4. **Preview**: View the parcel geometry in real-time
5. **Plot**: Add the parcel to your QGIS map

## Input Validation

- **Degrees**: Must be between 0 and 90
- **Minutes**: Must be between 0 and 59
- **Directions**: Automatically capitalized (N/S, E/W)
- **Distance**: Must be a positive number

## OCR Support

The plugin includes optional OCR functionality for digitizing technical descriptions from scanned TCTs. To use this feature:

1. Install Tesseract OCR on your system
2. Install required Python packages:
   ```bash
   pip install pytesseract Pillow opencv-python
   ```
3. Enable OCR in the plugin settings

## Development

### Requirements

- QGIS 3.x
- Python 3.x
- Required Python packages:
  - pandas
  - shapely
  - pytesseract (optional, for OCR)
  - Pillow (optional, for OCR)
  - opencv-python (optional, for OCR)

### Building from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/isaacenage/TitlePlotterPH.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Build resources:
   ```bash
   pyrcc5 resources.qrc -o resources.py
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the GNU General Public License v2.0 - see the [LICENSE](LICENSE) file for details.

## Author

- Isaac Enage (isaacenagework@gmail.com)

## Acknowledgments

- QGIS Plugin Builder
- Philippine Geodetic Engineers
- Open Source Community
