import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug mode
os.environ["MMST_DEBUG"] = "1"
os.environ["MMST_MEDIA_LIBRARY_ENHANCED"] = "1"

# Add custom exception hook to print all exceptions
def exception_hook(exctype, value, traceback):
    print(f"Exception: {exctype} - {value}")
    import traceback as tb
    tb.print_tb(traceback)
sys.excepthook = exception_hook

# Import and run the app
print("Starting MMST app with debug...")
from mmst.core.app import main
main()