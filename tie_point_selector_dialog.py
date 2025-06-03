# -*- coding: utf-8 -*-

import os
import pandas as pd
import json
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QHeaderView, QAbstractItemView, QComboBox
from qgis.PyQt.QtCore import pyqtSignal, Qt

# Load and normalize data at module level
try:
    json_path = os.path.join(os.path.dirname(__file__), "tiepoints.json")
    with open(json_path, "r") as f:
        raw_data = json.load(f)
    # Normalize key casing: "PROVINCE" → "Province"
    normalized_data = [{k.title(): v for k, v in row.items()} for row in raw_data]
    # Create DataFrame and clean data
    _TIEPOINT_DF = pd.DataFrame(normalized_data)
    
    # For entries with null Municipality, use the Province value as the Municipality
    _TIEPOINT_DF["Municipality"] = _TIEPOINT_DF.apply(
        lambda row: row["Province"] if pd.isna(row["Municipality"]) else row["Municipality"], 
        axis=1
    )
    
    # Remove rows with missing critical data
    _TIEPOINT_DF.dropna(subset=["Tie Point Name", "Province"], inplace=True)
    # Remove rows with empty strings in critical fields
    _TIEPOINT_DF = _TIEPOINT_DF[_TIEPOINT_DF["Tie Point Name"].astype(str).str.strip() != ""]
except Exception as e:
    print(f"Error loading tie points: {e}")
    _TIEPOINT_DF = pd.DataFrame()

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tie_point_selector_dialog_base.ui'))

class TiePointSelectorDialog(QDialog, FORM_CLASS):
    # Signal to emit when a tie point is selected
    tie_point_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        """Constructor."""
        super(TiePointSelectorDialog, self).__init__(parent)
        self.setupUi(self)
        self.setup_connections()
        self.setup_table_headers()
        self.setup_province_combo()
        # Initialize empty table
        self.tiePointTable.setRowCount(0)
        self.tiePointTable.setColumnCount(6)
        self.tiePointTable.setHorizontalHeaderLabels([
            "Tie Point Name", "Description", "Province", "Municipality", "Northing", "Easting"
        ])
        # Update status label
        self.statusLabel.setText("Status: No data loaded. Use search to find tie points.")

    def setup_connections(self):
        # Remove textChanged connections and add search button connection
        self.searchButton.clicked.connect(self.apply_filters)
        self.tiePointTable.itemDoubleClicked.connect(self.accept_selection)
        self.selectButton.clicked.connect(self.accept_selection)
        self.cancelButton.clicked.connect(self.reject)

    def setup_province_combo(self):
        """Set up the province ComboBox with unique provinces"""
        provinces = sorted(_TIEPOINT_DF["Province"].dropna().unique())
        self.provinceComboBox.addItem("")  # Blank = no filter
        self.provinceComboBox.addItems(provinces)

    def setup_table_headers(self):
        """Set up table headers and tooltips"""
        headers = ["Tie Point Name", "Description", "Province", "Municipality", "Northing", "Easting"]
        self.tiePointTable.setColumnCount(len(headers))
        self.tiePointTable.setHorizontalHeaderLabels(headers)

        # Set header resize mode and enable sorting
        header = self.tiePointTable.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tiePointTable.setSortingEnabled(True)

        # Set tooltips for headers
        tooltips = [
            "Name of the tie point (case and space insensitive)",
            "Description of the tie point (partial match)",
            "Province where the tie point is located (select from list)",
            "Municipality where the tie point is located (partial match)",
            "Northing coordinate of the tie point",
            "Easting coordinate of the tie point"
        ]
        for i, tooltip in enumerate(tooltips):
            self.tiePointTable.horizontalHeaderItem(i).setToolTip(tooltip)

        # Allow single row selection
        self.tiePointTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tiePointTable.setSelectionBehavior(QAbstractItemView.SelectRows)

    def populate_table(self, df):
        """Populate table with data from DataFrame"""
        # Clear existing contents and reset row count
        self.tiePointTable.clearContents()
        self.tiePointTable.setRowCount(0)

        # Set new row count and ensure column count
        self.tiePointTable.setRowCount(len(df))
        self.tiePointTable.setColumnCount(6)
        self.tiePointTable.setHorizontalHeaderLabels([
            "Tie Point Name", "Description", "Province", "Municipality", "Northing", "Easting"
        ])

        # Populate table with data
        for row_idx, (_, row) in enumerate(df.iterrows()):
            self.tiePointTable.setItem(row_idx, 0, QTableWidgetItem(str(row["Tie Point Name"])))
            self.tiePointTable.setItem(row_idx, 1, QTableWidgetItem(str(row["Description"])))
            self.tiePointTable.setItem(row_idx, 2, QTableWidgetItem(str(row["Province"])))
            self.tiePointTable.setItem(row_idx, 3, QTableWidgetItem(str(row["Municipality"])))
            self.tiePointTable.setItem(row_idx, 4, QTableWidgetItem(str(row["Northing"])))
            self.tiePointTable.setItem(row_idx, 5, QTableWidgetItem(str(row["Easting"])))

        # Resize columns to content after populating
        self.tiePointTable.resizeColumnsToContents()

        # Update status label
        self.statusLabel.setText(f"Status: {len(df)} rows shown")

    def apply_filters(self):
        """Apply filters based on input fields"""
        name_filter = self.nameInput.text().replace(" ", "").lower()
        description_filter = self.descriptionInput.text().strip().lower()
        municipality_filter = self.municipalityInput.text().strip().lower()
        province_filter = self.provinceComboBox.currentText().strip()

        df = _TIEPOINT_DF.copy()

        # Normalize name column for flexible matching
        df["__name"] = df["Tie Point Name"].astype(str).str.replace(" ", "").str.lower()

        # Apply filters
        if name_filter:
            df = df[df["__name"].str.contains(name_filter)]

        if description_filter:
            df = df[df["Description"].astype(str).str.lower().str.contains(description_filter)]

        if municipality_filter:
            df = df[df["Municipality"].astype(str).str.lower().str.contains(municipality_filter)]

        if province_filter:
            df = df[df["Province"] == province_filter]

        # Drop temporary columns
        df = df.drop(columns=["__name"])

        self.populate_table(df)

    def accept_selection(self):
        """Handle selection of a tie point"""
        current_row = self.tiePointTable.currentRow()
        if current_row >= 0:
            self.selected_row = {
                'name': self.tiePointTable.item(current_row, 0).text(),
                'description': self.tiePointTable.item(current_row, 1).text(),
                'province': self.tiePointTable.item(current_row, 2).text(),
                'municipality': self.tiePointTable.item(current_row, 3).text(),
                'northing': float(self.tiePointTable.item(current_row, 4).text()),
                'easting': float(self.tiePointTable.item(current_row, 5).text())
            }
            self.accept()

    def get_selected_row(self):
        """Return the selected tie point data"""
        return getattr(self, 'selected_row', None) 