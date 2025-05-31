from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QWidget, QGraphicsScene, QGraphicsPolygonItem, QGraphicsLineItem, QSizePolicy, QMessageBox, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, QLabel
from qgis.PyQt.QtGui import QPolygonF, QPen, QColor, QPainter
from qgis.PyQt.QtCore import Qt, QPointF, pyqtSignal, QVariant
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

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'Title Plotter - Philippine Land Titles_dialog_base.ui'))

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

def compute_deltas(deg, min_, dist, ns):
    """Calculate latitude and departure deltas for a single bearing line."""
    angle_rad = radians(deg + (min_ / 60))
    delta_lat = dist * cos(angle_rad) * (1 if ns.upper() == "N" else -1)
    delta_dep = dist * sin(angle_rad) * (1 if ns.upper() == "N" else -1)
    return round(delta_lat, 3), round(delta_dep, 3)

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
        except Exception as e:
            raise ValueError(f"Bearing row {i+1} has invalid input: {e}")

        delta_lat, delta_dep = compute_deltas(deg, min_, dist, ns)

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

        # Create input fields
        self.directionInput = QLineEdit()
        self.degreesInput = QLineEdit()
        self.minutesInput = QLineEdit()
        self.quadrantInput = QLineEdit()
        self.distanceInput = QLineEdit()

        # Set properties
        self.directionInput.setMaxLength(1)
        self.degreesInput.setMaxLength(2)
        self.minutesInput.setMaxLength(2)
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

        # Create delta labels
        self.deltaLatLabel = QLabel("ΔLat: 0.000")
        self.deltaDepLabel = QLabel("ΔDep: 0.000")
        self.deltaLatLabel.setFixedWidth(80)
        self.deltaDepLabel.setFixedWidth(80)

        # Create buttons
        add_btn = QPushButton("+")
        remove_btn = QPushButton("-")
        add_btn.setFixedWidth(30)
        remove_btn.setFixedWidth(30)

        # Add widgets to layout
        layout.addWidget(self.directionInput)
        layout.addWidget(self.degreesInput)
        layout.addWidget(self.minutesInput)
        layout.addWidget(self.quadrantInput)
        layout.addWidget(self.distanceInput)
        layout.addWidget(add_btn)
        layout.addWidget(remove_btn)
        
        # Add a small spacer between remove button and delta labels
        spacer = QWidget()
        spacer.setFixedWidth(12)
        layout.addWidget(spacer)
        
        layout.addWidget(self.deltaLatLabel)
        layout.addWidget(self.deltaDepLabel)

        # Connect signals
        self.distanceInput.textChanged.connect(self.update_deltas)
        add_btn.clicked.connect(self.parent().add_bearing_row)
        
        # Only connect remove button if not first row
        if not self.is_first_row:
            # Store reference to the dialog instance
            dialog = self.parent()
            if isinstance(dialog, TitlePlotterPhilippineLandTitlesDialog):
                remove_btn.clicked.connect(lambda _, row=self: dialog.remove_bearing_row(row))
        else:
            remove_btn.setEnabled(False)

        # Connect text changed signals to trigger WKT generation
        for input_field in [self.directionInput, self.degreesInput, self.minutesInput, 
                          self.quadrantInput, self.distanceInput]:
            input_field.textChanged.connect(self.parent().generate_wkt)

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
            dist = float(self.distanceInput.text().strip().replace(",", "."))

            # Calculate deltas
            delta_lat, delta_dep = compute_deltas(deg, min_, dist, ns)

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

        # Initialize bearing rows list
        self.bearing_rows = []
        
        # Connect signals
        self.openTiePointDialogButton.clicked.connect(self.open_tiepoint_selector)
        self.plotButton.clicked.connect(self.plot_on_map)

        # Replace QGraphicsView with QgsMapCanvas
        self.polygonPreview.setParent(None)
        self.polygonPreview.deleteLater()
        
        # Create preview canvas container
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize QgsMapCanvas with correct settings
        self.previewCanvas = QgsMapCanvas()
        self.previewCanvas.setCanvasColor(Qt.white)
        self.previewCanvas.enableAntiAliasing(True)
        self.previewCanvas.setWheelFactor(1.2)  # Optional zoom smoothness
        self.previewCanvas.setEnabled(True)
        self.previewCanvas.setMinimumHeight(250)
        self.previewCanvas.setMinimumWidth(600)
        preview_layout.addWidget(self.previewCanvas)
        
        # Add zoom to layer button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.zoomToLayerBtn = QPushButton("Zoom to Layer")
        self.zoomToLayerBtn.setMaximumWidth(120)
        self.zoomToLayerBtn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.zoomToLayerBtn)
        preview_layout.addLayout(button_layout)
        
        # Connect zoom button
        self.zoomToLayerBtn.clicked.connect(self.zoom_preview_to_layer)
        
        # Add preview container to main layout
        self.verticalLayout.insertWidget(3, preview_container)

        # Ensure bearingListLayout exists and is a QVBoxLayout
        self.bearingListLayout = self.scrollAreaWidgetContents.layout()
        if not isinstance(self.bearingListLayout, QVBoxLayout):
            self.bearingListLayout = QVBoxLayout(self.scrollAreaWidgetContents)

        # Set minimum height for the scroll area
        self.scrollArea.setMinimumHeight(300)

        # Set up initial row
        self.setup_initial_row()

        # Initialize tie point
        self.tie_point = None

        # Store the last generated WKT
        self.last_wkt = None
        
        # Initialize preview layer
        self.preview_layer = None

        # Remove the WKT output widget and Generate WKT button
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

    def add_bearing_row(self):
        """Add a new bearing input row."""
        row = BearingRowWidget(self)
        self.bearingListLayout.addWidget(row)
        self.bearing_rows.append(row)

    def remove_bearing_row(self, row_widget):
        """Remove a bearing input row."""
        if len(self.bearing_rows) > 1:  # Keep at least one row
            self.bearingListLayout.removeWidget(row_widget)
            row_widget.deleteLater()
            self.bearing_rows.remove(row_widget)

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
                    dist = float(row.distanceInput.text().strip().replace(",", "."))

                    # Calculate deltas
                    delta_lat, delta_dep = compute_deltas(deg, min_, dist, ns)

                    # Update current position
                    current_n += delta_lat
                    current_e += delta_dep

                    # Add to coordinates list
                    coords.append((current_e, current_n))

                except (ValueError, AttributeError) as e:
                    return

            # Check if we have enough points for a polygon
            if len(coords) < 3:
                return

            # Create polygon and generate WKT
            polygon = Polygon(coords)
            self.last_wkt = polygon.wkt
            
            # Update preview
            self.draw_preview(coords)

        except ValueError:
            pass
        except Exception:
            pass

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
        """Parses bearing components into an azimuth in degrees (0-360)."""
        try:
            deg = float(degrees)
            min = float(minutes)
            
            # Validate degrees and minutes ranges
            if not (0 <= deg < 360 and 0 <= min < 60):
                 print(f"Invalid degree or minute value: {degrees}° {minutes}'")
                 return None

            # Convert degrees and minutes to decimal degrees
            azimuth = deg + (min / 60.0)
            
            # Adjust based on quadrant
            direction = direction.strip().upper()
            quadrant = quadrant.strip().upper()
            
            if direction == 'N':
                if quadrant == 'E':
                    # North-East quadrant (0 to 90)
                    return azimuth
                elif quadrant == 'W':
                    # North-West quadrant (270 to 360)
                    return 360.0 - azimuth if azimuth != 0 else 0.0 # Handle N 0 W case
                else:
                     print(f"Invalid quadrant for North: {quadrant}")
                     return None
            elif direction == 'S':
                if quadrant == 'E':
                    # South-East quadrant (90 to 180)
                    return 180.0 - azimuth
                elif quadrant == 'W':
                    # South-West quadrant (180 to 270)
                    return 180.0 + azimuth
                else:
                     print(f"Invalid quadrant for South: {quadrant}")
                     return None
            elif direction == 'E' and not direction and not degrees and not minutes: # Special case for Due East (0° E or 90°) - generally not in DMS
                 if quadrant == 'N': return 90.0
                 elif quadrant == 'S': return 90.0
            elif direction == 'W' and not direction and not degrees and not minutes: # Special case for Due West (180° W or 270°) - generally not in DMS
                 if quadrant == 'N': return 270.0
                 elif quadrant == 'S': return 270.0
            elif direction == 'N' and not quadrant and not degrees and not minutes: return 0.0 # Due North
            elif direction == 'S' and not quadrant and not degrees and not minutes: return 180.0 # Due South

            # Invalid direction
            print(f"Invalid direction: {direction}")
            return None
            
        except ValueError:
            # Handle cases where conversion to float fails
            print(f"Invalid numeric value in bearing: {degrees}, {minutes}")
            return None
        except Exception as e:
             print(f"Error parsing bearing: {e}")
             return None

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
            if canvas:
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
                provider = layer.dataProvider()

                # Create and add feature
                feature = QgsFeature()
                geometry = QgsGeometry.fromWkt(self.last_wkt)

                # Validate geometry
                if not geometry.isGeosValid():
                    QMessageBox.warning(self, "Invalid Geometry", "The generated polygon is not valid.")
                    return

                feature.setGeometry(geometry)
                provider.addFeatures([feature])

                layer.updateExtents()
                QgsProject.instance().addMapLayer(layer)

                # Zoom to the new polygon
                canvas.setExtent(layer.extent())
                canvas.refresh()
            else:
                QMessageBox.warning(self, "Warning", "Could not access map canvas.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot polygon: {str(e)}") 