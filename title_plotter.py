# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TitlePlotter-PhilippineLandTitles
                                 A QGIS plugin
 Title Plotter - Philippine Land Titles a custom QGIS plugin designed to automate the plotting of land parcels using the official Philippine land title format. Built specifically for geodetic engineers, GIS analysts, and real estate professionals, this tool allows users to input technical descriptions (bearing-distance or metes-and-bounds format) and instantly generate accurate parcel geometries.

The plugin intelligently interprets common Philippine survey notations—such as those from TCTs and OCTs—and supports both PRS92 and WGS84 coordinate systems. It simplifies boundary plotting by automating bearing parsing, distance conversion, and closing error checks.

Whether you're working with Cadastral maps, mother lots, or subdivisions, PH Land Title Plotter provides a reliable and streamlined solution—right inside QGIS.

Key Features:
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2025-05-31
        git sha              : $Format:%H$
        copyright            : (C) 2025 by isaacenage
        email                : isaacenagework@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   The Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPainter, QPen, QColor
from qgis.PyQt.QtWidgets import QGraphicsScene, QGraphicsLineItem
from qgis.core import QgsGeometry, QgsFeature, QgsVectorLayer, QgsProject
import math
import os
from .dialogs.title_plotter_dialog import TitlePlotterPhilippineLandTitlesDialog
from .dialogs.tie_point_selector_dialog import TiePointSelectorDialog

# Initialize Qt resources from file resources.py
from . import resources

class TitlePlotterPhilippineLandTitles:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale_raw = QSettings().value('locale/userLocale')
        locale = str(locale_raw)[0:2] if locale_raw else 'en'
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'TitlePlotter-PhilippineLandTitles_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Title Plotter - Philippine Land Titles')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        self.dlg = TitlePlotterPhilippineLandTitlesDialog(self.iface)
        self.scene = QGraphicsScene()
        self.current_points = []
        self.setup_connections()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QtWidgets.QApplication.translate('TitlePlotterPhilippineLandTitles', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        # Initialize the dialog
        self.dlg = TitlePlotterPhilippineLandTitlesDialog(self.iface)
        
        # Create the action that will start plugin configuration
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon.png")
        self.action = QAction(QIcon(icon_path), "Title Plotter – Philippine Land Titles", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(self.menu, self.action)
        self.actions.append(self.action)

        # will be set False in run()
        self.first_start = True

        self.setup_connections()

    def setup_connections(self):
        """Set up signal connections for the dialog."""
        self.dlg.openTiePointDialogButton.clicked.connect(self.open_tiepoint_selector)
        self.dlg.plotButton.clicked.connect(self.dlg.plot_on_map)

    def add_bearing_row(self):
        # Create a new row of bearing inputs
        row_layout = QtWidgets.QHBoxLayout()
        
        direction = QtWidgets.QLineEdit()
        direction.setMaxLength(1)
        direction.setPlaceholderText("N/S")
        
        degrees = QtWidgets.QLineEdit()
        degrees.setMaxLength(3)
        degrees.setPlaceholderText("Deg")
        
        minutes = QtWidgets.QLineEdit()
        minutes.setMaxLength(2)
        minutes.setPlaceholderText("Min")
        
        quadrant = QtWidgets.QLineEdit()
        quadrant.setMaxLength(1)
        quadrant.setPlaceholderText("E/W")
        
        distance = QtWidgets.QLineEdit()
        distance.setPlaceholderText("Distance (m)")
        
        delete_btn = QtWidgets.QPushButton("-")
        delete_btn.clicked.connect(lambda: self.delete_bearing_row(row_layout))
        
        row_layout.addWidget(direction)
        row_layout.addWidget(degrees)
        row_layout.addWidget(minutes)
        row_layout.addWidget(quadrant)
        row_layout.addWidget(distance)
        row_layout.addWidget(delete_btn)
        
        self.dlg.bearingListLayout.addLayout(row_layout)
        self.update_preview()

    def delete_bearing_row(self, row_layout):
        # Remove all widgets in the row
        while row_layout.count():
            item = row_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Remove the layout itself
        self.dlg.bearingListLayout.removeItem(row_layout)
        self.update_preview()

    def parse_bearing(self, direction, degrees, minutes, quadrant):
        try:
            deg = float(degrees)
            min = float(minutes)
            azimuth = deg + (min / 60.0)
            
            if direction.upper() == 'N':
                if quadrant.upper() == 'E':
                    return azimuth
                else:  # W
                    return 360 - azimuth
            else:  # S
                if quadrant.upper() == 'E':
                    return 180 - azimuth
                else:  # W
                    return 180 + azimuth
        except ValueError:
            return None

    def calculate_point(self, start_point, bearing, distance):
        # Convert bearing to radians
        bearing_rad = math.radians(bearing)
        
        # Calculate new point
        dx = distance * math.sin(bearing_rad)
        dy = distance * math.cos(bearing_rad)
        
        return (start_point[0] + dx, start_point[1] + dy)

    def update_preview(self):
        self.scene.clear()
        self.current_points = []
        
        try:
            # Get tie point coordinates
            northing = float(self.dlg.tiePointNorthingInput.text())
            easting = float(self.dlg.tiePointEastingInput.text())
            current_point = (easting, northing)
            self.current_points.append(current_point)
            
            # Process each bearing row
            for i in range(self.dlg.bearingListLayout.count()):
                row_layout = self.dlg.bearingListLayout.itemAt(i)
                if not isinstance(row_layout, QtWidgets.QHBoxLayout):
                    continue
                
                # Get values from widgets
                direction = row_layout.itemAt(0).widget().text()
                degrees = row_layout.itemAt(1).widget().text()
                minutes = row_layout.itemAt(2).widget().text()
                quadrant = row_layout.itemAt(3).widget().text()
                distance = row_layout.itemAt(4).widget().text()
                
                if not all([direction, degrees, minutes, quadrant, distance]):
                    continue
                
                try:
                    bearing = self.parse_bearing(direction, degrees, minutes, quadrant)
                    distance = float(distance)
                    
                    if bearing is not None:
                        next_point = self.calculate_point(current_point, bearing, distance)
                        self.current_points.append(next_point)
                        
                        # Draw line
                        line = QGraphicsLineItem(
                            current_point[0], -current_point[1],
                            next_point[0], -next_point[1]
                        )
                        line.setPen(QPen(QColor(0, 0, 255), 2))
                        self.scene.addItem(line)
                        
                        current_point = next_point
                except ValueError:
                    continue
            
            # Draw closing line if we have points
            if len(self.current_points) > 2:
                line = QGraphicsLineItem(
                    self.current_points[-1][0], -self.current_points[-1][1],
                    self.current_points[0][0], -self.current_points[0][1]
                )
                line.setPen(QPen(QColor(0, 0, 255), 2))
                self.scene.addItem(line)
            
            # Fit view to scene
            self.dlg.polygonPreview.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            
        except ValueError:
            pass

    def open_tiepoint_selector(self):
        dialog = TiePointSelectorDialog()
        if dialog.exec_():
            selected_row = dialog.get_selected_row()
            if selected_row:
                self.dlg.tiePointNorthingInput.setText(str(selected_row['northing']))
                self.dlg.tiePointEastingInput.setText(str(selected_row['easting']))
                self.update_preview()

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = TitlePlotterPhilippineLandTitlesDialog(self.iface)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
