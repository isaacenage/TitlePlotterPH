from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QTextEdit
from qgis.PyQt.QtGui import QPixmap, QImage
from qgis.PyQt.QtCore import Qt, QBuffer, QIODevice
import os
import re
import sys
import webbrowser
from io import BytesIO
import cv2
import numpy as np

# Try importing OCR-related modules with detailed error reporting
OCR_ENABLED = False
missing_modules = []
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def check_tesseract():
    """Check if Tesseract OCR is installed and accessible."""
    if not os.path.exists(TESSERACT_PATH):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Tesseract OCR Not Found")
        msg.setText("This plugin requires Tesseract OCR to extract bearings and distances from scanned TCT documents.")
        msg.setInformativeText(
            "Please install Tesseract OCR manually from:\n"
            "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
            "After installing, ensure the folder is located at:\n"
            "C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n\n"
            "Then restart QGIS."
        )
        
        # Add download button
        download_btn = msg.addButton("Open Download Page", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)
        
        msg.exec_()
        
        # Handle download button click
        if msg.clickedButton() == download_btn:
            webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")
        
        return False
    return True

print("Starting OCR module imports...")

try:
    import pytesseract
    if check_tesseract():
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        print("Successfully imported pytesseract")
        print(f"Tesseract version: {pytesseract.get_tesseract_version()}")
        # Set Tesseract path explicitly
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    else:
        raise Exception("Tesseract OCR not found")
except ImportError as e:
    missing_modules.append("pytesseract")
    print(f"Failed to import pytesseract: {str(e)}")
except Exception as e:
    missing_modules.append("pytesseract")
    print(f"Error with pytesseract: {str(e)}")

try:
    from PIL import Image
    print("Successfully imported PIL.Image")
except ImportError as e:
    missing_modules.append("Pillow")
    print(f"Failed to import PIL.Image: {str(e)}")

try:
    import cv2
    print("Successfully imported cv2")
    print(f"OpenCV version: {cv2.__version__}")
except ImportError as e:
    missing_modules.append("opencv-python")
    print(f"Failed to import cv2: {str(e)}")

try:
    import numpy as np
    print("Successfully imported numpy")
    print(f"Numpy version: {np.__version__}")
except ImportError as e:
    missing_modules.append("numpy")
    print(f"Failed to import numpy: {str(e)}")

# Check if all required modules are available
if not missing_modules:
    OCR_ENABLED = True
    print("All OCR modules successfully imported")
else:
    print(f"Missing modules: {', '.join(missing_modules)}")
    print(f"Python path: {sys.path}")

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'TCT_OCR_Dialog.ui'))

class TCTOCRDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(TCTOCRDialog, self).__init__(parent)
        self.setupUi(self)
        
        # Store the parent dialog reference
        self.parent_dialog = parent
        
        # Initialize image data
        self.current_image = None
        
        # Connect signals
        self.uploadButton.clicked.connect(self.upload_image)
        self.pasteButton.clicked.connect(self.paste_from_clipboard)
        self.doneButton.clicked.connect(self.process_image)
        self.cancelButton.clicked.connect(self.reject)
        
        # Add QTextEdit for raw OCR text (hidden by default)
        self.rawOcrTextEdit = QTextEdit(self)
        self.rawOcrTextEdit.setReadOnly(True)
        self.rawOcrTextEdit.hide()
        self.rawOcrTextEdit.setMinimumHeight(100)
        self.rawOcrTextEdit.setMaximumHeight(200)
        self.verticalLayout.addWidget(self.rawOcrTextEdit)
        
        # Enable/disable OCR-related buttons based on module availability
        if not OCR_ENABLED:
            self.uploadButton.setEnabled(False)
            self.pasteButton.setEnabled(False)
            error_msg = f"OCR unavailable. Missing modules: {', '.join(missing_modules)}"
            self.uploadButton.setToolTip(error_msg)
            self.pasteButton.setToolTip(error_msg)
            print(error_msg)
        else:
            self.uploadButton.setEnabled(True)
            self.pasteButton.setEnabled(True)
            print("OCR buttons enabled")

    def upload_image(self):
        """Handle image upload from file."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select TCT Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        
        if file_name:
            self.load_image(file_name)

    def paste_from_clipboard(self):
        """Handle image paste from clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        image = clipboard.image()
        
        if not image.isNull():
            self.current_image = image
            self.display_image(image)
        else:
            QMessageBox.warning(self, "Error", "No image found in clipboard.")

    def load_image(self, file_path):
        """Load and display image from file."""
        try:
            # Load image using PIL for OCR
            self.current_image = Image.open(file_path)
            
            # Convert to QImage for display
            qimage = QImage(file_path)
            self.display_image(qimage)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")

    def display_image(self, image):
        """Display image in the preview area."""
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            self.imagePreview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.imagePreview.setPixmap(scaled_pixmap)

    def process_image(self):
        """Process the image using OCR and extract bearing-distance data."""
        if not self.current_image:
            QMessageBox.warning(self, "Error", "No image to process.")
            return
            
        # Hide raw OCR text box
        self.rawOcrTextEdit.hide()

        try:
            # Convert PIL Image to NumPy array first
            if isinstance(self.current_image, QImage):
                # Convert QImage to PIL Image using BytesIO
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                self.current_image.save(buffer, "PNG")
                bytes_io = BytesIO(buffer.data())
                pil_image = Image.open(bytes_io)
            else:
                pil_image = self.current_image

            # Convert PIL Image to NumPy array
            img_np = np.array(pil_image)
            
            # Convert RGB to BGR for OpenCV if needed
            if len(img_np.shape) == 3:
                 img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            elif len(img_np.shape) == 2:
                 # If it's already grayscale, convert to BGR anyway for preprocess
                 img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)

            # Extract bearing-distance data
            bearings, raw_text = self.extract_bearings(img_np)
            
            if bearings:
                print(f"Successfully extracted {len(bearings)} bearing lines.")
                # Add bearings to parent dialog
                self.add_bearings_to_parent(bearings)
                self.accept()
            else:
                print("No bearing-distance data found after extraction.")
                QMessageBox.warning(self, "Warning", "No bearing-distance data found in the image after parsing.")
                # Show raw OCR text in the text edit
                self.rawOcrTextEdit.setPlainText(raw_text)
                self.rawOcrTextEdit.show()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process image: {str(e)}")

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess the image for better OCR results.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Preprocessed image as numpy array
        """
        # Grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Thresholding
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return thresh

    def extract_bearings(self, image):
        """Extract bearing-distance data from OCR text using a tolerant regex and filter results."""
        bearings = []
        
        # Preprocess image for better OCR
        processed_img = self.preprocess(image)
        
        # Perform OCR with PSM mode 6 (Assume a single block of text)
        raw_text = pytesseract.image_to_string(processed_img, config='--psm 6')
        
        # Log the raw input text for debugging
        print("OCR raw text:", raw_text)
        
        # Pre-clean the OCR text
        cleaned_text = raw_text.replace('%', '°') \
                           .replace('’', "'") \
                           .replace('o', '°') \
                           .replace(',', '.') \
                           .replace('O', '0') \
                           .replace('|', '1') \
                           .replace('"', '"') \
                           .replace('°°', '°') \
                           .replace('  ', ' ')

        # Use a forgiving regex pattern to extract the lines
        bearing_pattern = re.compile(
            r"""
            (?P<ns>[NS])                # N or S
            [\s.]*                      # Optional spacing/dot
            (?P<deg>\d{1,3})            # Degrees (changed to 1-3 digits)
            [^\dA-Za-z]?[°%o]?[^\dA-Za-z]?  # Common OCR substitutions
            (?P<min>\d{1,2})            # Minutes
            [^\dA-Za-z]?[''7]?          # Common OCR substitutions for '
            [\s.]*                      # Optional spacing
            (?P<ew>[EW])                # E or W
            [\s,]*                      # Optional spacing/comma
            (?P<dist>\d+(\.\d+)?)       # Distance (e.g. 123.45)
            [\s]*[mM]?                 # Optional 'm' or 'M'
            """,
            re.IGNORECASE | re.VERBOSE
        )
        
        # Match all lines from OCR output
        matches = bearing_pattern.findall(cleaned_text)

        print(f"Found {len(matches)} bearing-distance matches.")

        # Process matches and convert to desired format
        for match in matches:
            try:
                direction_str, degrees_str, _, minutes_str, _, quadrant_str, dist_str, _ = match
                
                # Clean and validate extracted values
                direction = direction_str.strip().upper()
                quadrant = quadrant_str.strip().upper()
                degrees = int(degrees_str.strip())
                minutes = int(minutes_str.strip())
                distance = float(dist_str.strip())
                
                # Enhanced validation with logging
                if direction in ['N', 'S'] and quadrant in ['E', 'W']:
                    # Allow 0-359 for degrees temporarily for better parsing, will validate against bearing rules later
                    if 0 <= minutes <= 59:
                        if distance > 0:
                            bearing = {
                                'direction': direction,
                                'degrees': degrees, # Keep as int for now
                                'minutes': minutes, # Keep as int for now
                                'quadrant': quadrant,
                                'distance': distance
                            }
                            bearings.append(bearing)
                            print(f"✓ Valid bearing found: {direction} {degrees}° {minutes}' {quadrant} {distance}m")
                        else:
                            print(f"✗ Invalid distance: {distance}m")
                    else:
                        print(f"✗ Invalid minutes: {minutes}'")
                else:
                    print(f"✗ Invalid direction/quadrant: {direction}/{quadrant}")

            except (ValueError, IndexError) as e:
                print(f"✗ Error processing match {match}: {str(e)}")
                continue

        return bearings, raw_text

    def add_bearings_to_parent(self, bearings):
        """Add extracted bearings to the parent dialog's bearing rows."""
        if not self.parent_dialog:
            return
            
        # Clear existing rows except the first one
        while self.parent_dialog.bearingListLayout.count() > 1:
            row = self.parent_dialog.bearingListLayout.itemAt(1)
            if row:
                self.parent_dialog.remove_bearing_row(row.widget())
        
        # Add new bearing rows
        for bearing in bearings:
            self.parent_dialog.add_bearing_row()
            row = self.parent_dialog.bearingListLayout.itemAt(
                self.parent_dialog.bearingListLayout.count() - 1
            ).widget()
            
            # Set values
            row.directionInput.setText(bearing['direction'])
            row.degreesInput.setText(str(bearing['degrees']))
            row.minutesInput.setText(str(bearing['minutes']))
            row.quadrantInput.setText(bearing['quadrant'])
            row.distanceInput.setText(str(bearing['distance']))
            
        # Update preview
        self.parent_dialog.generate_wkt()

    def resizeEvent(self, event):
        """Handles resize event for the dialog."""
        super().resizeEvent(event)
        # Adjust raw OCR text edit visibility on resize if needed, or keep hidden/shown as per logic
        if self.rawOcrTextEdit.isVisible():
            self.rawOcrTextEdit.updateGeometry() 