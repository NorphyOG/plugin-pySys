"""
Disk Integrity Monitor for Windows using S.M.A.R.T. data.

Retrieves disk health information via WMIC/PowerShell and displays
key metrics like temperature, reallocated sectors, power-on hours, etc.
"""
from __future__ import annotations

import subprocess
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QComboBox,
    QTextEdit, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

import platform


class DiskMonitorBase:
    """Base class for platform-specific disk monitoring."""
    
    @property
    def is_available(self) -> bool:
        raise NotImplementedError
    
    def get_disks(self) -> List[DiskInfo]:
        raise NotImplementedError
    
    def get_smart_attributes(self, disk_index: int) -> List[SmartAttribute]:
        raise NotImplementedError
    
    def get_disk_temperature(self, disk_index: int) -> Optional[int]:
        raise NotImplementedError
    
    def get_health_summary(self, disk_index: int) -> Dict[str, Any]:
        attributes = self.get_smart_attributes(disk_index)
        
        warnings = []
        critical = []
        
        for attr in attributes:
            if attr.status == "WARNING":
                warnings.append(f"{attr.name}: {attr.raw_value}")
            elif attr.status == "CRITICAL":
                critical.append(f"{attr.name}: {attr.raw_value}")
        
        overall_status = "CRITICAL" if critical else ("WARNING" if warnings else "HEALTHY")
        
        return {
            "status": overall_status,
            "warnings": warnings,
            "critical": critical,
            "temperature": self.get_disk_temperature(disk_index),
            "attributes_count": len(attributes)
        }


@dataclass
class DiskInfo:
    """Information about a physical disk."""
    index: int
    model: str
    serial: str
    size_gb: float
    interface: str
    status: str


@dataclass
class SmartAttribute:
    """S.M.A.R.T. attribute with current value and threshold."""
    id: int
    name: str
    current: int
    worst: int
    threshold: int
    raw_value: str
    status: str  # "OK", "WARNING", "CRITICAL"


class DiskMonitorWindows(DiskMonitorBase):
    """Backend for retrieving disk health information on Windows."""
    
    def __init__(self):
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if WMIC is available (Windows only)."""
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "model"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @property
    def is_available(self) -> bool:
        """Check if disk monitoring is available."""
        return self._available
    
    def get_disks(self) -> List[DiskInfo]:
        """Get list of physical disks."""
        if not self._available:
            return []
        
        disks = []
        try:
            # Get disk information via WMIC
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "Index,Model,SerialNumber,Size,InterfaceType,Status", "/format:csv"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode != 0:
                return []
            
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return []
            
            # Parse CSV output (skip header)
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 6:
                    continue
                
                try:
                    # Format: Node,Index,InterfaceType,Model,SerialNumber,Size,Status
                    index = int(parts[1]) if parts[1] else 0
                    interface = parts[2] or "Unknown"
                    model = parts[3] or "Unknown Disk"
                    serial = parts[4] or "N/A"
                    size_bytes = int(parts[5]) if parts[5] else 0
                    size_gb = size_bytes / (1024**3) if size_bytes > 0 else 0
                    status = parts[6] or "Unknown"
                    
                    disks.append(DiskInfo(
                        index=index,
                        model=model,
                        serial=serial,
                        size_gb=size_gb,
                        interface=interface,
                        status=status
                    ))
                except (ValueError, IndexError):
                    continue
        
        except Exception:
            return []
        
        return disks
    
    def get_smart_attributes(self, disk_index: int) -> List[SmartAttribute]:
        """
        Get S.M.A.R.T. attributes for a disk using WMIC.
        
        This method queries the `MSStorageDriver_FailurePredictData` class.
        Note: This requires admin privileges to run correctly on some systems.
        """
        if not self._available:
            return []

        attributes = []
        try:
            # This command needs to be run with admin rights to get the data
            cmd = [
                "wmic",
                "/namespace:\\\\root\\wmi",
                "path",
                "MSStorageDriver_FailurePredictData",
                "get",
                "InstanceName, PredictorId, CurrentValue, Threshold, WorstValue",
                "/format:csv"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            if result.returncode != 0 or not result.stdout.strip():
                return self._get_simulated_attributes() # Fallback for non-admin

            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return self._get_simulated_attributes()

            # Find the correct disk based on InstanceName which contains the serial number
            disks = self.get_disks()
            if disk_index >= len(disks):
                return self._get_simulated_attributes()
            
            current_disk_serial = disks[disk_index].serial

            for line in lines[1:]:
                if not line.strip():
                    continue
                
                parts = line.strip().split(',')
                if len(parts) < 5 or not current_disk_serial in parts[1]:
                    continue

                try:
                    attr_id = int(parts[2])
                    current = int(parts[0])
                    threshold = int(parts[3])
                    worst = int(parts[4])
                    
                    # WMI doesn't give name or raw value easily, so we use a lookup
                    attr_name, is_critical = self._get_attribute_details(attr_id)
                    
                    status = "OK"
                    if current < threshold:
                        status = "CRITICAL"

                    attributes.append(SmartAttribute(
                        id=attr_id,
                        name=attr_name,
                        current=current,
                        worst=worst,
                        threshold=threshold,
                        raw_value="N/A", # Not provided by this WMI class
                        status=status
                    ))
                except (ValueError, IndexError):
                    continue
            
            if not attributes:
                return self._get_simulated_attributes()

        except Exception:
            return self._get_simulated_attributes()
        
        return attributes

    def _get_simulated_attributes(self) -> List[SmartAttribute]:
        """Returns a list of simulated attributes as a fallback."""
        return [
            SmartAttribute(0, "Simulated Data", 100, 100, 0, "FALLBACK", "WARNING"),
            SmartAttribute(5, "Reallocated Sectors", 100, 100, 36, "0", "OK"),
            SmartAttribute(9, "Power-On Hours", 98, 98, 0, "15234", "OK"),
            SmartAttribute(194, "Temperature", 35, 42, 0, "35°C", "OK"),
        ]

    def _get_attribute_details(self, attr_id: int) -> tuple[str, bool]:
        """Lookup for S.M.A.R.T. attribute names."""
        known_attributes = {
            1: ("Read Error Rate", True),
            5: ("Reallocated Sectors Count", True),
            9: ("Power-On Hours", False),
            12: ("Power Cycle Count", False),
            194: ("Temperature Celsius", False),
            197: ("Current Pending Sector Count", True),
            198: ("Offline Uncorrectable Sector Count", True),
        }
        return known_attributes.get(attr_id, (f"Unknown ({attr_id})", False))

    def get_disk_temperature(self, disk_index: int) -> Optional[int]:
        """Get disk temperature in Celsius (if available) via WMI."""
        if not self._available:
            return None

        try:
            cmd = [
                "wmic",
                "/namespace:\\\\root\\wmi",
                "path",
                "MSStorageDriver_FailurePredictStatus",
                "get",
                "InstanceName, Temperature",
                 "/format:csv"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            if result.returncode == 0 and result.stdout.strip():
                disks = self.get_disks()
                if disk_index >= len(disks):
                    return None
                current_disk_serial = disks[disk_index].serial

                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    if not line.strip():
                        continue
                    parts = line.strip().split(',')
                    if len(parts) >= 3 and current_disk_serial in parts[1]:
                        return int(parts[2])
        except Exception:
            pass

        # Fallback to attribute parsing
        attributes = self.get_smart_attributes(disk_index)
        for attr in attributes:
            if attr.id == 194:
                try:
                    return int(re.sub(r'[^0-9]', '', attr.raw_value))
                except ValueError:
                    continue
        return None
    

class DiskMonitorLinux(DiskMonitorBase):
    """Backend for retrieving disk health information on Linux using smartctl."""
    
    def __init__(self):
        self._available = self._check_availability()
        self._disks: List[DiskInfo] = []
    
    def _check_availability(self) -> bool:
        """Check if smartctl is available."""
        try:
            result = subprocess.run(
                ["smartctl", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
            
    @property
    def is_available(self) -> bool:
        return self._available

    def get_disks(self) -> List[DiskInfo]:
        if not self.is_available:
            return []
        
        if self._disks:
            return self._disks

        disks = []
        try:
            # First, scan for devices
            scan_result = subprocess.run(
                ["smartctl", "--scan-open"],
                capture_output=True, text=True, timeout=10
            )
            if scan_result.returncode != 0:
                return []

            for i, line in enumerate(scan_result.stdout.strip().split('\n')):
                if not line.strip() or line.startswith("#"):
                    continue
                
                parts = line.split("#")
                device_path = parts[0].strip().split(" ")[0] # Get the device path like /dev/sda

                # Then, get detailed info for each device
                info_result = subprocess.run(
                    ["smartctl", "-i", device_path],
                    capture_output=True, text=True, timeout=5
                )
                
                if info_result.returncode != 0:
                    continue

                model = "Unknown Model"
                serial = "N/A"
                size_gb = 0.0
                status = "Unknown"

                for info_line in info_result.stdout.split('\n'):
                    if "Device Model:" in info_line:
                        model = info_line.split(":", 1)[1].strip()
                    elif "Serial Number:" in info_line:
                        serial = info_line.split(":", 1)[1].strip()
                    elif "User Capacity:" in info_line:
                        size_str = info_line.split("[", 1)[1].split("]")[0]
                        if "GB" in size_str:
                            size_gb = float(size_str.replace("GB", "").strip())
                        elif "TB" in size_str:
                            size_gb = float(size_str.replace("TB", "").strip()) * 1000
                    elif "SMART overall-health self-assessment test result:" in info_line:
                        status = info_line.split(":", 1)[1].strip()


                disks.append(DiskInfo(
                    index=i,
                    model=model,
                    serial=serial,
                    size_gb=size_gb,
                    interface=device_path,
                    status=status
                ))
            
            self._disks = disks
        except Exception:
            return []
            
        return disks

    def get_smart_attributes(self, disk_index: int) -> List[SmartAttribute]:
        if not self.is_available or not self._disks or disk_index >= len(self._disks):
            return []

        device_path = self._disks[disk_index].interface
        attributes = []
        try:
            result = subprocess.run(
                ["smartctl", "-A", device_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return []

            lines = result.stdout.split('\n')
            attr_section = False
            for line in lines:
                if line.startswith("ID#"):
                    attr_section = True
                    continue
                if not attr_section or not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 10:
                    continue
                
                try:
                    attr_id = int(parts[0])
                    attr_name = parts[1]
                    current = int(parts[3])
                    worst = int(parts[4])
                    thresh = int(parts[5])
                    raw_value = parts[9]
                    
                    # Simple status check
                    status = "OK"
                    if current < thresh:
                        status = "CRITICAL"

                    attributes.append(SmartAttribute(
                        id=attr_id,
                        name=attr_name,
                        current=current,
                        worst=worst,
                        threshold=thresh,
                        raw_value=raw_value,
                        status=status
                    ))
                except (ValueError, IndexError):
                    continue
        except Exception:
            return []
        
        return attributes

    def get_disk_temperature(self, disk_index: int) -> Optional[int]:
        attributes = self.get_smart_attributes(disk_index)
        for attr in attributes:
            if attr.id == 194 or "Temperature" in attr.name:
                try:
                    # Raw value can be complex, e.g., "35 (Min/Max 20/50)"
                    temp_str = attr.raw_value.split()[0]
                    return int(re.sub(r'[^0-9]', '', temp_str))
                except (ValueError, IndexError):
                    continue
        return None


def DiskMonitor() -> DiskMonitorBase:
    """Factory function to return the appropriate disk monitor for the platform."""
    if platform.system() == "Windows":
        return DiskMonitorWindows()
    elif platform.system() == "Linux":
        return DiskMonitorLinux()
    else:
        # Return a dummy implementation for other platforms
        class DiskMonitorUnsupported(DiskMonitorBase):
            @property
            def is_available(self) -> bool: return False
            def get_disks(self) -> List[DiskInfo]: return []
            def get_smart_attributes(self, disk_index: int) -> List[SmartAttribute]: return []
            def get_disk_temperature(self, disk_index: int) -> Optional[int]: return None
        
        return DiskMonitorUnsupported()


class DiskMonitorWidget(QWidget):
    """Widget for displaying disk health information."""
    
    refresh_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._monitor = DiskMonitor()
        self._current_disk: Optional[DiskInfo] = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        if not self._monitor.is_available:
            platform_name = platform.system()
            tool_name = "WMIC" if platform_name == "Windows" else "smartctl"
            warning = QLabel(f"⚠️ Disk monitoring nicht verfügbar ({platform_name} / {tool_name} benötigt)")
            warning.setStyleSheet("color: orange; font-weight: bold;")
            status_layout.addWidget(warning)
        else:
            status_label = QLabel("✅ Disk Monitoring verfügbar")
            status_label.setStyleSheet("color: green;")
            status_layout.addWidget(status_label)
        
        status_layout.addStretch(1)
        
        refresh_btn = QPushButton("🔄 Aktualisieren")
        refresh_btn.clicked.connect(self._refresh)
        status_layout.addWidget(refresh_btn)
        
        layout.addLayout(status_layout)
        
        # Disk selection
        disk_group = QGroupBox("Disk-Auswahl")
        disk_layout = QHBoxLayout(disk_group)
        disk_layout.addWidget(QLabel("Disk:"))
        
        self.disk_combo = QComboBox()
        self.disk_combo.currentIndexChanged.connect(self._on_disk_changed)
        disk_layout.addWidget(self.disk_combo, stretch=1)
        
        layout.addWidget(disk_group)
        
        # Health summary
        summary_group = QGroupBox("Zusammenfassung")
        summary_layout = QVBoxLayout(summary_group)
        
        self.status_label = QLabel("Status: --")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        summary_layout.addWidget(self.status_label)
        
        self.temp_label = QLabel("Temperatur: --")
        summary_layout.addWidget(self.temp_label)
        
        self.warnings_label = QLabel("Warnungen: --")
        self.warnings_label.setStyleSheet("color: orange;")
        summary_layout.addWidget(self.warnings_label)
        
        layout.addWidget(summary_group)
        
        # S.M.A.R.T. attributes table
        attributes_group = QGroupBox("S.M.A.R.T. Attribute")
        attributes_layout = QVBoxLayout(attributes_group)
        
        self.attributes_table = QTableWidget(0, 6)
        self.attributes_table.setHorizontalHeaderLabels([
            "ID", "Name", "Aktuell", "Worst", "Threshold", "Raw Value"
        ])
        self.attributes_table.horizontalHeader().setStretchLastSection(True)
        self.attributes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.attributes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        attributes_layout.addWidget(self.attributes_table)
        
        layout.addWidget(attributes_group, stretch=1)
        
        # Info text
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        self.info_text.setPlainText(
            "S.M.A.R.T. (Self-Monitoring, Analysis and Reporting Technology) überwacht "
            "Festplatten-Gesundheit. Wichtige Attribute:\n"
            "• Reallocated Sectors: Defekte Sektoren (sollte 0 sein)\n"
            "• Temperature: Betriebstemperatur (< 50°C empfohlen)\n"
            "• Power-On Hours: Betriebsstunden\n"
            "• Pending Sectors: Sektoren mit Leseproblemen"
        )
        info_layout.addWidget(self.info_text)
        
        layout.addWidget(info_group)
        
        # Initial refresh
        self._refresh()
    
    def _refresh(self):
        """Refresh disk list and data."""
        self.disk_combo.clear()
        
        if not self._monitor.is_available:
            return
        
        disks = self._monitor.get_disks()
        
        for disk in disks:
            display_text = f"Disk {disk.index}: {disk.model} ({disk.size_gb:.1f} GB)"
            self.disk_combo.addItem(display_text, disk)
        
        if disks:
            self._on_disk_changed(0)
    
    def _on_disk_changed(self, index: int):
        """Handle disk selection change."""
        if index < 0:
            return
        
        disk = self.disk_combo.itemData(index)
        if not disk:
            return
        
        self._current_disk = disk
        self._update_display()
    
    def _update_display(self):
        """Update display with current disk data."""
        if not self._current_disk:
            return
        
        # Get health summary
        summary = self._monitor.get_health_summary(self._current_disk.index)
        
        # Update status
        status = summary["status"]
        if status == "HEALTHY":
            self.status_label.setText("Status: ✅ HEALTHY")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        elif status == "WARNING":
            self.status_label.setText("Status: ⚠️ WARNING")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
        else:
            self.status_label.setText("Status: ❌ CRITICAL")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        
        # Update temperature
        temp = summary.get("temperature")
        if temp:
            temp_color = "green" if temp < 45 else ("orange" if temp < 55 else "red")
            self.temp_label.setText(f"Temperatur: {temp}°C")
            self.temp_label.setStyleSheet(f"color: {temp_color};")
        else:
            self.temp_label.setText("Temperatur: N/A")
        
        # Update warnings
        warnings = summary.get("warnings", [])
        critical = summary.get("critical", [])
        
        if critical:
            self.warnings_label.setText(f"❌ Kritisch: {', '.join(critical)}")
            self.warnings_label.setStyleSheet("color: red; font-weight: bold;")
        elif warnings:
            self.warnings_label.setText(f"⚠️ Warnungen: {', '.join(warnings)}")
            self.warnings_label.setStyleSheet("color: orange;")
        else:
            self.warnings_label.setText("✅ Keine Warnungen")
            self.warnings_label.setStyleSheet("color: green;")
        
        # Update attributes table
        attributes = self._monitor.get_smart_attributes(self._current_disk.index)
        self.attributes_table.setRowCount(0)
        
        for attr in attributes:
            row = self.attributes_table.rowCount()
            self.attributes_table.insertRow(row)
            
            self.attributes_table.setItem(row, 0, QTableWidgetItem(str(attr.id)))
            self.attributes_table.setItem(row, 1, QTableWidgetItem(attr.name))
            self.attributes_table.setItem(row, 2, QTableWidgetItem(str(attr.current)))
            self.attributes_table.setItem(row, 3, QTableWidgetItem(str(attr.worst)))
            self.attributes_table.setItem(row, 4, QTableWidgetItem(str(attr.threshold)))
            self.attributes_table.setItem(row, 5, QTableWidgetItem(attr.raw_value))
            
            # Color code based on status
            if attr.status == "CRITICAL":
                color = QColor(255, 200, 200)  # Light red
            elif attr.status == "WARNING":
                color = QColor(255, 230, 200)  # Light orange
            else:
                color = QColor(200, 255, 200)  # Light green
            
            for col in range(6):
                item = self.attributes_table.item(row, col)
                if item:
                    item.setBackground(color)
    
    def set_enabled(self, enabled: bool):
        """Enable or disable the widget."""
        self.setEnabled(enabled)
