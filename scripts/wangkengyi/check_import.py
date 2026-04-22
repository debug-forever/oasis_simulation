
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("visualization_system/backend").resolve()))

print("Attempting to import api.simulation...")
try:
    import api.simulation
    print("Successfully imported api.simulation")
except Exception as e:
    print(f"Failed to import api.simulation: {e}")
    import traceback
    traceback.print_exc()
