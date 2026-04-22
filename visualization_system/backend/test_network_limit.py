
import sys
import os
import time
import json

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import get_db_manager
from utils.data_aggregation import build_relationship_network

def test_large_limit():
    try:
        db = get_db_manager()
        print(f"Connected to DB: {db.db_path}")
        
        start_time = time.time()
        print("Requesting network with limit=2000...")
        
        # Test with limit 2000
        data = build_relationship_network(db, limit=2000, min_followers=0)
        
        duration = time.time() - start_time
        print(f"Query took {duration:.4f} seconds")
        
        print(f"Nodes: {len(data['nodes'])}")
        print(f"Links: {len(data['links'])}")
        
        if len(data['nodes']) == 0:
            print("WARNING: No nodes returned!")
        else:
             print(f"Sample node: {data['nodes'][0]['display_name']}")

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_large_limit()
