from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QWidget, QGraphicsScene, QGraphicsPolygonItem, QGraphicsLineItem, QSizePolicy, QMessageBox, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, QLabel
from qgis.PyQt.QtGui import QPolygonF, QPen, QColor, QPainter, QIntValidator, QRegExpValidator
from qgis.PyQt.QtCore import Qt, QPointF, pyqtSignal, QVariant, QBuffer, QIODevice, QRegExp
import os
import math
from shapely.geometry import Polygon
from math import sin, cos, radians
from qgis.core import (
    QgsPointXY, 
    QgsGeometry, 
    QgsFeature, 
    QgsVectorLayer, 
    QgsProject, 
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsApplication
)
from qgis.gui import QgsMapCanvas
from qgis.core import QgsFillSymbol

# Attempt to import TiePointSelectorDialog, handle potential ImportError later if the file is missing
try:
    from .tie_point_selector_dialog import TiePointSelectorDialog
except ImportError:
    TiePointSelectorDialog = None
    print("Warning: tie_point_selector_dialog.py not found. Tie point selection functionality will be disabled.")

# Make sure shapely is installed in your QGIS environment
# You might need to install it using QGIS's Python terminal or OSGeo4W shell:
# pip install shapely
try:
    from shapely.geometry import Polygon
except ImportError:
    Polygon = None
    print("Warning: shapely library not found. WKT generation functionality will be disabled.")

# Import OCR dialog
try:
    from .TCT_OCR_Dialog import TCTOCRDialog
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'forms', 'title_plotter_dialog_base.ui'))

def bearing_to_azimuth(direction_ns, degrees, minutes, direction_ew):
    """Convert bearing to azimuth in degrees using Excel's method."""
    angle = int(degrees) + int(minutes) / 60
    if direction_ns == "N" and direction_ew == "E":
        return angle
    elif direction_ns == "S" and direction_ew == "E":
        return 180 - angle
    elif direction_ns == "S" and direction_ew == "W":
        return 180 + angle
    elif direction_ns == "N" and direction_ew == "W":
        return 360 - angle
    else:
        raise ValueError("Invalid bearing direction combination.")

def calculate_deltas(ns, deg, minute, ew, distance):
    """Calculate latitude and departure deltas for a single bearing line with correct signs."""
    angle_degrees = deg + (minute / 60)
    angle_radians = math.radians(angle_degrees)

    delta_lat = distance * math.cos(angle_radians)
    delta_dep = distance * math.sin(angle_radians)

    # Apply sign based on direction
    if ns.upper() == 'S':
        delta_lat *= -1
    if ew.upper() == 'W':
        delta_dep *= -1

    return round(delta_lat, 3), round(delta_dep, 3) # Round to 3 decimal places

def generate_coordinates(tie_easting, tie_northing, bearing_rows):
    """Generate coordinates using Excel's cumulative delta method."""
    coords = []

    current_e = tie_easting
    current_n = tie_northing

    for i, row in enumerate(bearing_rows):
        try:
            ns = row.directionInput.text().strip().upper()
            deg = int(row.degreesInput.text().strip())
            min_ = int(row.minutesInput.text().strip())
            ew = row.quadrantInput.text().strip().upper()
            dist = float(row.distanceInput.text().strip().replace(",", "."))
            
            # Validate degrees and minutes
            if deg < 0 or deg > 90:
                raise ValueError(f"Degrees must be between 0 and 90 (got {deg})")
            if min_ < 0 or min_ > 59:
                raise ValueError(f"Minutes must be between 0 and 59 (got {min_})")
                
        except Exception as e:
            raise ValueError(f"Bearing row {i+1} has invalid input: {e}")

        # Use the new calculate_deltas function
        delta_lat, delta_dep = calculate_deltas(ns, deg, min_, ew, dist)

        current_n += delta_lat
        current_e += delta_dep

        coords.append((current_e, current_n))

    return coords

class BearingRowWidget(QWidget):
    """Widget for a single bearing input row with delta calculations."""
    def __init__(self, parent=None, is_first_row=False):
        super(BearingRowWidget, self).__init__(parent)
        self.is_first_row = is_first_row
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)  # Reduced spacing between all elements

        # Add Line Label
        self.lineLabel = QLabel("")
        self.lineLabel.setFixedWidth(60)
        layout.addWidget(self.lineLabel)

        # Create input fields
        self.directionInput = QLineEdit()
        self.degreesInput = QLineEdit()
        self.minutesInput = QLineEdit()
        self.quadrantInput = QLineEdit()
        self.distanceInput = QLineEdit()

        # Set properties
        self.directionInput.setMaxLength(1)
        self.degreesInput.setMaxLength(3) # Allow up to 3 digits for 0-90 (e.g., 90)
        self.minutesInput.setMaxLength(2) # Allow up to 2 digits for 0-59 (e.g., 59)
        self.quadrantInput.setMaxLength(1)

        # Set fixed widths
        self.directionInput.setFixedWidth(30)  # N/S
        self.degreesInput.setFixedWidth(40)    # Deg
        self.minutesInput.setFixedWidth(40)    # Min
        self.quadrantInput.setFixedWidth(30)   # E/W
        self.distanceInput.setFixedWidth(80)   # Distance

        # Set placeholders
        self.directionInput.setPlaceholderText("N/S")
        self.degreesInput.setPlaceholderText("Deg")
        self.minutesInput.setPlaceholderText("Min")
        self.quadrantInput.setPlaceholderText("E/W")
        self.distanceInput.setPlaceholderText("Distance")

        # Add Validators
        self.directionInput.setValidator(QRegExpValidator(QRegExp("^[NSns]$")))
        # Use QIntValidator with ranges for degrees and minutes
        self.degreesInput.setValidator(QIntValidator(0, 90, self))
        self.minutesInput.setValidator(QIntValidator(0, 59, self))
        self.quadrantInput.setValidator(QRegExpValidator(QRegExp("^[EWew]$")))

        # Create delta labels
        self.deltaLatLabel = QLabel("ΔLat: 0.000")
        self.deltaDepLabel = QLabel("ΔDep: 0.000")
        self.deltaLatLabel.setFixedWidth(80)
        self.deltaDepLabel.setFixedWidth(80)

        # Create buttons
        self.add_btn = QPushButton("+")
        self.remove_btn = QPushButton("-")
        self.add_btn.setFixedWidth(30)
        self.remove_btn.setFixedWidth(30)

        # Add widgets to layout
        layout.addWidget(self.directionInput)
        layout.addWidget(self.degreesInput)
        layout.addWidget(self.minutesInput)
        layout.addWidget(self.quadrantInput)
        layout.addWidget(self.distanceInput)
        layout.addWidget(self.add_btn)
        layout.addWidget(self.remove_btn)
        
        # Add a small spacer between remove button and delta labels
        spacer = QWidget()
        spacer.setFixedWidth(12)
        layout.addWidget(spacer)
        
        layout.addWidget(self.deltaLatLabel)
        layout.addWidget(self.deltaDepLabel)

        # Connect signals
        self.distanceInput.textChanged.connect(self.update_deltas)
        self.directionInput.textChanged.connect(self.update_deltas) # Also update deltas on direction change
        self.degreesInput.textChanged.connect(self.update_deltas) # Also update deltas on degrees change
        self.minutesInput.textChanged.connect(self.update_deltas) # Also update deltas on minutes change
        self.quadrantInput.textChanged.connect(self.update_deltas) # Also update deltas on quadrant change
        
        # Add validation signals
        self.degreesInput.textChanged.connect(self.validate_degrees)
        self.minutesInput.textChanged.connect(self.validate_minutes)
        self.directionInput.textChanged.connect(self.auto_capitalize_direction)
        self.quadrantInput.textChanged.connect(self.auto_capitalize_quadrant)
        
        self.add_btn.clicked.connect(self.parent().add_bearing_row)
        
        # Only connect remove button if not first row
        if not self.is_first_row:
            # Store reference to the dialog instance
            dialog = self.parent()
            if isinstance(dialog, TitlePlotterPhilippineLandTitlesDialog):
                self.remove_btn.clicked.connect(lambda _, row=self: dialog.remove_bearing_row(row))
        else:
            self.remove_btn.setEnabled(False)

        # Connect text changed signals to trigger WKT generation
        for input_field in [self.directionInput, self.degreesInput, self.minutesInput, 
                          self.quadrantInput, self.distanceInput]:
            input_field.textChanged.connect(self.parent().generate_wkt)

    def validate_degrees(self):
        """Validate degrees input and update UI accordingly."""
        try:
            value = int(self.degreesInput.text())
            if value > 90:
                self.degreesInput.setStyleSheet("background-color: #8b0000; color: white")
                self.add_btn.setEnabled(False)
            else:
                self.degreesInput.setStyleSheet("")
                self.add_btn.setEnabled(True)
        except ValueError:
            self.degreesInput.setStyleSheet("")
            self.add_btn.setEnabled(True)

    def validate_minutes(self):
        """Validate minutes input and update UI accordingly."""
        try:
            value = int(self.minutesInput.text())
            if value > 59:
                self.minutesInput.setStyleSheet("background-color: #8b0000; color: white")
                self.add_btn.setEnabled(False)
            else:
                self.minutesInput.setStyleSheet("")
                self.add_btn.setEnabled(True)
        except ValueError:
            self.minutesInput.setStyleSheet("")
            self.add_btn.setEnabled(True)

    def auto_capitalize_direction(self):
        """Auto-capitalize N/S input."""
        text = self.directionInput.text().upper()
        if text != self.directionInput.text():
            self.directionInput.setText(text)

    def auto_capitalize_quadrant(self):
        """Auto-capitalize E/W input."""
        text = self.quadrantInput.text().upper()
        if text != self.quadrantInput.text():
            self.quadrantInput.setText(text)

    def reset_values(self):
        """Reset all input values to empty and clear styles."""
        self.directionInput.setText("")
        self.degreesInput.setText("")
        self.minutesInput.setText("")
        self.quadrantInput.setText("")
        self.distanceInput.setText("")
        self.degreesInput.setStyleSheet("")
        self.minutesInput.setStyleSheet("")
        self.deltaLatLabel.setText("ΔLat: 0.000")
        self.deltaDepLabel.setText("ΔDep: 0.000")
        self.add_btn.setEnabled(True)

    def update_deltas(self):
        """Update delta values when all fields are filled."""
        try:
            # Check if all fields have values
            if not all([
                self.directionInput.text().strip(),
                self.degreesInput.text().strip(),
                self.minutesInput.text().strip(),
                self.quadrantInput.text().strip(),
                self.distanceInput.text().strip()
            ]):
                return

            # Get values
            ns = self.directionInput.text().strip().upper()
            deg = int(self.degreesInput.text().strip())
            min_ = int(self.minutesInput.text().strip())
            ew = self.quadrantInput.text().strip().upper()
            dist = float(self.distanceInput.text().strip().replace(",", "."))

            # Additional validation for degrees and minutes
            if deg < 0 or deg > 90:
                self.degreesInput.setText("0")  # Reset to 0 if out of range
                deg = 0
            if min_ < 0 or min_ > 59:
                self.minutesInput.setText("0")  # Reset to 0 if out of range
                min_ = 0

            # Calculate deltas using the updated function
            delta_lat, delta_dep = calculate_deltas(ns, deg, min_, ew, dist)

            # Update labels
            self.deltaLatLabel.setText(f"ΔLat: {delta_lat:.3f}")
            self.deltaDepLabel.setText(f"ΔDep: {delta_dep:.3f}")

        except ValueError:
            # Clear labels if calculation fails
            self.deltaLatLabel.setText("ΔLat: 0.000")
            self.deltaDepLabel.setText("ΔDep: 0.000")

class TitlePlotterPhilippineLandTitlesDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TitlePlotterPhilippineLandTitlesDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)

        # Set style for the WKT preview label (loaded from UI)
        self.labelWKT.setStyleSheet("background-color: #2b2b2b; color: #dcdcdc; padding: 6px;")
        self.labelWKT.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Initialize bearing rows list
        self.bearing_rows = []
        
        # Connect signals
        self.openTiePointDialogButton.clicked.connect(self.open_tiepoint_selector)
        self.plotButton.clicked.connect(self.plot_on_map)

        # --- Rearrange Layout --- 
        # Get references to widgets loaded from UI
        horizontalLayout_tiepoints = self.horizontalLayout # Northing/Easting layout
        technicalDescriptionLabel = self.technicalDescriptionLabel
        scrollArea_bearings = self.scrollArea # Bearing inputs scroll area
        plotButton = self.plotButton
        # labelWKT is already referenced as self.labelWKT

        # Remove widgets from the original layout structure loaded by setupUi
        # They will be re-added in the desired order
        self.verticalLayout.removeWidget(technicalDescriptionLabel)
        self.verticalLayout.removeWidget(scrollArea_bearings)
        self.verticalLayout.removeWidget(plotButton)
        self.verticalLayout.removeWidget(self.labelWKT) # Remove labelWKT to add it in order
        # Note: horizontalLayout_tiepoints might be the first item, leaving it might work, but explicitly adding gives control
        # Let's remove and re-add it for clarity
        self.verticalLayout.removeItem(horizontalLayout_tiepoints) # Remove the layout item

        # Create the OCR button (if available) - needs to be before adding to layout
        if OCR_AVAILABLE:
            self.ocrButton = QPushButton("Upload TCT Image")
            self.ocrButton.clicked.connect(self.open_ocr_dialog)
        else:
            self.ocrButton = QPushButton("Upload TCT Image")
            self.ocrButton.setEnabled(False)
            self.ocrButton.setToolTip("OCR unavailable. Required modules not installed.")

        # Create a container for the preview canvas and zoom button
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        # Create a horizontal layout for the zoom and new buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()  # Add stretch to push buttons to the right

        # Initialize QgsMapCanvas for the visual preview
        self.previewCanvas = QgsMapCanvas(preview_container)
        self.previewCanvas.setCanvasColor(Qt.white)
        self.previewCanvas.enableAntiAliasing(True)
        self.previewCanvas.setWheelFactor(1.2)  # Optional zoom smoothness
        self.previewCanvas.setEnabled(True)
        self.previewCanvas.setMinimumHeight(250)
        preview_layout.addWidget(self.previewCanvas)

        # Add zoom to layer button with proper layout
        self.zoomToLayerBtn = QPushButton("Zoom to Layer")
        self.zoomToLayerBtn.setFixedSize(100, 24)
        self.zoomToLayerBtn.setStyleSheet("background-color: #444; color: white; border-radius: 4px; font-size: 10pt;")
        self.zoomToLayerBtn.clicked.connect(self.zoom_preview_to_layer)
        button_layout.addWidget(self.zoomToLayerBtn)

        # Add New button
        self.newButton = QPushButton("New")
        self.newButton.setFixedSize(100, 24)
        self.newButton.setStyleSheet("background-color: #444; color: white; border-radius: 4px; font-size: 10pt;")
        self.newButton.clicked.connect(self.reset_plotter)
        button_layout.addWidget(self.newButton)
        
        # Add the button layout to the preview layout
        preview_layout.addLayout(button_layout)

        # Add widgets/layouts to the main vertical layout in the desired order
        self.verticalLayout.addLayout(horizontalLayout_tiepoints) # Northing/Easting
        self.verticalLayout.addWidget(self.ocrButton) # Upload TCT Image Button
        self.verticalLayout.addWidget(technicalDescriptionLabel) # Technical Description Area Label
        self.verticalLayout.addWidget(scrollArea_bearings) # Bearing Inputs
        self.verticalLayout.addWidget(preview_container) # Polygon Preview Canvas
        self.verticalLayout.addWidget(self.labelWKT) # WKT Output Label
        self.verticalLayout.addWidget(plotButton) # Plot on Map Button
        # --- End Rearrange Layout ---

        # Ensure bearingListLayout exists and is a QVBoxLayout (inside scrollArea_bearings)
        # This is already handled by setupUi, but re-checking doesn't hurt
        self.bearingListLayout = self.scrollAreaWidgetContents.layout()
        if not isinstance(self.bearingListLayout, QVBoxLayout):
             # This case should ideally not happen if UI is correctly set up
            self.bearingListLayout = QVBoxLayout(self.scrollAreaWidgetContents)
            self.bearingListLayout.setAlignment(Qt.AlignTop) # Ensure alignment
            self.bearingListLayout.setContentsMargins(0,0,0,0) # Ensure margins
            self.bearingListLayout.setSpacing(2) # Ensure spacing

        # Set minimum height for the scroll area
        # This is set in UI, but can be enforced here if needed
        # self.scrollArea.setMinimumHeight(300)

        # Set up initial row (this adds to bearingListLayout, which is inside scrollArea)
        self.setup_initial_row()

        # Initialize tie point
        self.tie_point = None

        # Store the last generated WKT
        self.last_wkt = None
        
        # Initialize preview layer (for the QgsMapCanvas)
        self.preview_layer = None

        # Remove the old WKT output widget and Generate WKT button
        # These were removed in a previous step, keeping this check for safety
        if hasattr(self, 'wktOutput'):
            self.wktOutput.setParent(None)
            self.wktOutput.deleteLater()
        if hasattr(self, 'generateWKTButton'):
            self.generateWKTButton.setParent(None)
            self.generateWKTButton.deleteLater()

    def setup_initial_row(self):
        """Set up the initial bearing row."""
        row = BearingRowWidget(self, is_first_row=True)
        self.bearingListLayout.addWidget(row)
        self.bearing_rows.append(row)
        self.update_line_labels()

    def add_bearing_row(self):
        """Add a new bearing input row."""
        row = BearingRowWidget(self)
        self.bearingListLayout.addWidget(row)
        self.bearing_rows.append(row)
        self.update_line_labels()

    def remove_bearing_row(self, row_widget):
        """Remove a bearing input row."""
        if len(self.bearing_rows) > 1:  # Keep at least one row
            self.bearingListLayout.removeWidget(row_widget)
            row_widget.deleteLater()
            self.bearing_rows.remove(row_widget)
            self.update_line_labels()

    def update_line_labels(self):
        """Update the line labels based on their index."""
        for i, row in enumerate(self.bearing_rows):
            if i == 0:
                row.lineLabel.setText("TP - 1")
            elif i == len(self.bearing_rows) - 1:
                row.lineLabel.setText(f"{i} - 1")
            else:
                row.lineLabel.setText(f"{i} - {i+1}")

    def get_bearing_data(self):
        """Get all bearing data from the rows"""
        data = []
        for row in self.bearing_rows:
            row_layout = row.layout()
            direction = row_layout.itemAt(0).widget().text().strip().upper()
            degrees = row_layout.itemAt(1).widget().text().strip()
            minutes = row_layout.itemAt(2).widget().text().strip()
            quadrant = row_layout.itemAt(3).widget().text().strip().upper()
            distance = row_layout.itemAt(4).widget().text().strip()
            
            if all([direction, degrees, minutes, quadrant, distance]):
                try:
                    data.append({
                        'direction': direction,
                        'degrees': int(degrees),
                        'minutes': int(minutes),
                        'quadrant': quadrant,
                        'distance': float(distance)
                    })
                except ValueError:
                    continue
        return data

    def draw_preview(self, coords):
        """Draw the polygon preview on the QgsMapCanvas."""
        if not coords or len(coords) < 2:
            return

        # Create a memory layer for the preview
        self.preview_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "Preview Layer", "memory")
        provider = self.preview_layer.dataProvider()

        # Create polygon geometry
        polygon = QPolygonF([QPointF(x, y) for x, y in coords])
        geometry = QgsGeometry.fromPolygonXY([[QgsPointXY(p.x(), p.y()) for p in polygon]])
        
        # Create and add feature
        feature = QgsFeature()
        feature.setGeometry(geometry)
        provider.addFeatures([feature])
        
        # Update layer extent
        self.preview_layer.updateExtents()
        
        # Set consistent style for the preview layer
        symbol = QgsFillSymbol.createSimple({
            'color': '0,0,0,0',  # Transparent fill
            'outline_color': 'red',
            'outline_width': '2'
        })
        self.preview_layer.renderer().setSymbol(symbol)
        self.preview_layer.triggerRepaint()
        
        # Set layer to canvas
        self.previewCanvas.setLayers([self.preview_layer])
        self.previewCanvas.zoomToFeatureExtent(self.preview_layer.extent())
        self.previewCanvas.refresh()

    def generate_wkt(self):
        """Generate WKT using Excel's coordinate calculation method."""
        try:
            # Get tie point coordinates
            tie_n = float(self.tiePointNorthingInput.text().strip().replace(",", "."))
            tie_e = float(self.tiePointEastingInput.text().strip().replace(",", "."))

            # Initialize coordinates list and current position
            coords = []
            current_n = tie_n
            current_e = tie_e

            # Process all bearing rows except the last one
            for row in self.bearing_rows[:-1]:
                try:
                    # Get values from the row
                    ns = row.directionInput.text().strip().upper()
                    deg = int(row.degreesInput.text().strip())
                    min_ = int(row.minutesInput.text().strip())
                    ew = row.quadrantInput.text().strip().upper()
                    dist = float(row.distanceInput.text().strip().replace(",", "."))

                    # Calculate deltas
                    delta_lat, delta_dep = calculate_deltas(ns, deg, min_, ew, dist)

                    # Update current position
                    current_n += delta_lat
                    current_e += delta_dep

                    # Add to coordinates list
                    coords.append((current_e, current_n))

                except (ValueError, AttributeError) as e:
                    return

            # Check if we have enough points for a polygon
            if len(coords) < 3:
                self.labelWKT.setText("Insufficient points for a polygon (minimum 3)")
                # Clear the preview layer as it's not a valid polygon
                if self.preview_layer and self.preview_layer.isValid():
                    QgsProject.instance().removeMapLayer(self.preview_layer)
                    self.preview_layer = None
                    self.previewCanvas.setLayers([])
                    self.previewCanvas.refresh()
                return

            # Create polygon and generate WKT
            # Ensure coordinates are in (Easting, Northing) format for WKT
            wkt_coords = ', '.join([f'{x} {y}' for x, y in coords])
            # Add the starting point to close the polygon
            if coords:
                 wkt_coords += f', {coords[0][0]} {coords[0][1]}'

            self.last_wkt = f"POLYGON (({wkt_coords}))"

            # Update the WKT preview label
            self.labelWKT.setText(self.last_wkt)

            # Update visual preview (draw the polygon on the map canvas)
            self.draw_preview(coords)

        except ValueError:
            self.labelWKT.setText("Error: Invalid numeric input")
        except Exception as e:
            self.labelWKT.setText(f"An unexpected error occurred: {str(e)}")

    def open_tiepoint_selector(self):
        """Opens the tie point selection dialog."""
        if TiePointSelectorDialog is None:
            QtWidgets.QMessageBox.warning(self, "Dependency Missing", "The tie point selector dialog file (tie_point_selector_dialog.py) was not found.")
            return

        dialog = TiePointSelectorDialog(self)
        if dialog.exec_(): # exec_() returns QDialog.Accepted or QDialog.Rejected
            selected_row = dialog.get_selected_row()
            if selected_row:
                self.tie_point = selected_row
                self.tiePointNorthingInput.setText(str(selected_row.get('northing', '')))
                self.tiePointEastingInput.setText(str(selected_row.get('easting', '')))
                # Update preview after selecting a tie point
                self.generate_wkt()

    def parse_bearing(self, direction, degrees, minutes, quadrant):
        """Parse bearing components into azimuth."""
        try:
            # Convert to integers and validate
            deg = int(degrees)
            min_ = int(minutes)
            
            # Validate degrees and minutes
            if deg < 0 or deg > 90:
                raise ValueError(f"Degrees must be between 0 and 90 (got {deg})")
            if min_ < 0 or min_ > 59:
                raise ValueError(f"Minutes must be between 0 and 59 (got {min_})")
                
            # Calculate azimuth
            angle = deg + (min_ / 60)
            
            if direction.upper() == "N" and quadrant.upper() == "E":
                return angle
            elif direction.upper() == "S" and quadrant.upper() == "E":
                return 180 - angle
            elif direction.upper() == "S" and quadrant.upper() == "W":
                return 180 + angle
            elif direction.upper() == "N" and quadrant.upper() == "W":
                return 360 - angle
            else:
                raise ValueError(f"Invalid bearing direction combination: {direction}{quadrant}")
        except ValueError as e:
            raise ValueError(f"Invalid bearing: {e}")

    def calculate_point(self, start_point, bearing_azimuth, distance):
        """Calculates the next point based on a starting point, azimuth, and distance.
        Bearing azimuth should be in degrees.
        Returns a tuple (x, y) or None if inputs are invalid.
        """
        try:
            # Normalize decimal separator in distance
            distance = float(str(distance).replace(",", "."))
            if bearing_azimuth is None or distance < 0:
                return None
                
            # Convert azimuth from degrees to radians for trigonometric functions
            azimuth_rad = math.radians(bearing_azimuth)
            
            # Calculate displacements (Easting is X, Northing is Y)
            dx = distance * math.sin(azimuth_rad)
            dy = distance * math.cos(azimuth_rad)
            
            next_x = start_point[0] + dx
            next_y = start_point[1] + dy
            
            return (next_x, next_y)
            
        except ValueError:
            # Handle cases where distance conversion fails
            print(f"Invalid distance value: {distance}")
            return None
        except Exception as e:
             print(f"Error calculating point: {e}")
             return None

    def calculate_coordinates(self):
        """Parses bearing/distance inputs from all rows and calculates the polygon coordinates.
        Returns a list of (x, y) tuples or an empty list if inputs are invalid.
        """
        coords = []
        try:
            # Get starting tie point coordinates (Easting, Northing)
            easting_text = self.tiePointEastingInput.text().strip().replace(",", ".")
            northing_text = self.tiePointNorthingInput.text().strip().replace(",", ".")
            
            if not easting_text or not northing_text:
                 self.wktOutput.setPlainText("Error: Tie point coordinates are required.")
                 return []

            start_easting = float(easting_text)
            start_northing = float(northing_text)
            current_point = (start_easting, start_northing)
            coords.append(current_point)

            # Iterate through bearing input rows
            layout = self.bearingListLayout
            if layout is None:
                print("Error: bearingListLayout is not initialized.")
                return []

            for i in range(layout.count()):
                row_item = layout.itemAt(i)
                if row_item and row_item.widget():
                    row_widget = row_item.widget()
                    row_layout = row_widget.layout()
                    
                    if row_layout and row_layout.count() >= 5:
                        # Get values from the QLineEdit widgets in the row
                        direction = row_layout.itemAt(0).widget().text()
                        degrees = row_layout.itemAt(1).widget().text()
                        minutes = row_layout.itemAt(2).widget().text()
                        quadrant = row_layout.itemAt(3).widget().text()
                        # Normalize decimal separator in distance
                        distance = row_layout.itemAt(4).widget().text().strip().replace(",", ".")

                        # Check if essential fields are filled for this row
                        if not any([direction, degrees, minutes, quadrant, distance]):
                            continue
                            
                        if not all([direction, degrees, minutes, quadrant, distance]):
                             self.wktOutput.setPlainText(f"Error: Incomplete bearing input in row {i+1}.")
                             return []

                        # Parse bearing and calculate the next point
                        bearing_azimuth = self.parse_bearing(direction, degrees, minutes, quadrant)
                        
                        if bearing_azimuth is None:
                             self.wktOutput.setPlainText(f"Error: Invalid bearing format in row {i+1}.")
                             return []

                        next_point = self.calculate_point(current_point, bearing_azimuth, distance)

                        if next_point:
                            coords.append(next_point)
                            current_point = next_point
                        else:
                            self.wktOutput.setPlainText(f"Error: Invalid distance value in row {i+1}.")
                            return []

            return coords

        except ValueError:
            self.wktOutput.setPlainText("Error: Invalid numeric input found.")
            return []
        except Exception as e:
            self.wktOutput.setPlainText(f"An unexpected error occurred during coordinate calculation: {e}")
            return []

    def zoom_preview_to_layer(self):
        """Zoom the preview canvas to the extent of the preview layer."""
        if self.preview_layer and self.preview_layer.isValid():
            self.previewCanvas.setExtent(self.preview_layer.extent())
            self.previewCanvas.refresh()

    def plot_on_map(self):
        """Plot the polygon on the map canvas."""
        if not self.last_wkt:
            QMessageBox.warning(self, "Error", "No valid polygon to plot.")
            return

        try:
            # Get the map canvas from the main window and check its CRS
            canvas = self.iface.mapCanvas()
            if not canvas:
                QMessageBox.warning(self, "Warning", "Could not access map canvas.")
                return

            canvas_crs = canvas.mapSettings().destinationCrs()

            # Check if the canvas CRS is EPSG:4326 (WGS84)
            if canvas_crs.authid() == "EPSG:4326":
                QMessageBox.warning(self, "Invalid Projection", "Please switch the map projection to a local coordinate system (not WGS84 / EPSG:4326).")
                return

            # Remove existing "Title Plot Preview" layer if it exists
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Title Plot Preview":
                    QgsProject.instance().removeMapLayer(layer)

            # Create a new memory layer with the canvas CRS
            layer = QgsVectorLayer(f"Polygon?crs={canvas_crs.authid()}", "Title Plot Preview", "memory")
            
            # Add attribute field for feature identification
            layer.dataProvider().addAttributes([QgsField("name", QVariant.String)])
            layer.updateFields()

            # Create and add feature
            feature = QgsFeature()
            
            # Parse WKT and create geometry
            geometry = QgsGeometry.fromWkt(self.last_wkt)
            
            # Validate geometry
            if not geometry or geometry.isEmpty():
                QMessageBox.warning(self, "Invalid Geometry", "The generated polygon is empty or invalid.")
                return

            if not geometry.isGeosValid():
                QMessageBox.warning(self, "Invalid Geometry", "The generated polygon is not valid.")
                return

            # Set geometry and attributes
            feature.setGeometry(geometry)
            feature.setAttributes(["Title Plot"])

            # Add feature to layer
            layer.dataProvider().addFeatures([feature])
            
            # Update layer extent and add to project
            layer.updateExtents()
            QgsProject.instance().addMapLayer(layer)

            # Set layer style (similar to QuickWKT)
            symbol = QgsFillSymbol.createSimple({
                'color': '255,0,0,50',  # Semi-transparent red
                'outline_color': 'red',
                'outline_width': '1'
            })
            layer.renderer().setSymbol(symbol)
            layer.triggerRepaint()

            # Zoom to the new polygon
            canvas.setExtent(layer.extent())
            canvas.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot polygon: {str(e)}")

    def open_ocr_dialog(self):
        """Open the OCR dialog for TCT image processing."""
        if not OCR_AVAILABLE:
            QMessageBox.warning(self, "OCR Unavailable", 
                              "Required OCR modules (pytesseract, Pillow, opencv-python) are not installed.")
            return
            
        # Import check_tesseract function
        from .TCT_OCR_Dialog import check_tesseract
        
        # Check if Tesseract is installed
        if not check_tesseract():
            return
            
        dialog = TCTOCRDialog(self)
        dialog.exec_() 

    def resizeEvent(self, event):
        """Handles resize event for the dialog."""
        super().resizeEvent(event) 

    def reset_plotter(self):
        """Reset all inputs and clear the plotter."""
        # Clear tie point inputs
        self.tiePointNorthingInput.setText("")
        self.tiePointEastingInput.setText("")
        self.tie_point = None

        # Clear all bearing rows except the first one
        while len(self.bearing_rows) > 1:
            self.remove_bearing_row(self.bearing_rows[-1])

        # Reset the first row
        if self.bearing_rows:
            self.bearing_rows[0].reset_values()

        # Clear WKT and preview
        self.labelWKT.setText("")
        self.last_wkt = None
        if self.preview_layer and self.preview_layer.isValid():
            QgsProject.instance().removeMapLayer(self.preview_layer)
            self.preview_layer = None
            self.previewCanvas.setLayers([])
            self.previewCanvas.refresh() 