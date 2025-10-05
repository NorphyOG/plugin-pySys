import unittest
from unittest.mock import MagicMock, patch
import platform

from mmst.plugins.system_tools.disk_monitor import (
    DiskMonitor,
    DiskMonitorBase,
    DiskMonitorWindows,
    DiskMonitorLinux,
)


class TestDiskMonitor(unittest.TestCase):
    def test_factory(self):
        """Test the DiskMonitor factory."""
        if platform.system() == "Windows":
            self.assertIsInstance(DiskMonitor(), DiskMonitorWindows)
        elif platform.system() == "Linux":
            self.assertIsInstance(DiskMonitor(), DiskMonitorLinux)
        else:
            self.assertIsInstance(DiskMonitor(), DiskMonitorBase)

    @patch("platform.system", return_value="Windows")
    def test_windows_instance(self, _):
        """Test if DiskMonitor returns a Windows instance."""
        monitor = DiskMonitor()
        self.assertIsInstance(monitor, DiskMonitorWindows)

    @patch("platform.system", return_value="Linux")
    def test_linux_instance(self, _):
        """Test if DiskMonitor returns a Linux instance."""
        monitor = DiskMonitor()
        self.assertIsInstance(monitor, DiskMonitorLinux)

    @patch("platform.system", return_value="Darwin")
    def test_unsupported_instance(self, _):
        """Test if DiskMonitor returns a base instance for unsupported systems."""
        monitor = DiskMonitor()
        self.assertIsInstance(monitor, DiskMonitorBase)
        self.assertFalse(monitor.is_available)


if __name__ == "__main__":
    unittest.main()
