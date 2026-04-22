
import sys
import os
import json

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import get_db_manager
from utils.data_aggregation import build_relationship_network

def test_network():
    try:
        with open('network_debug.log', 'w', encoding='utf-8') as f:
            db = get_db_manager()
            f.write(f"Connected to DB: {db.db_path}\n")
            
            # Test with default parameters
            data = build_relationship_network(db, limit=100, min_followers=0)
            
            f.write(f"Nodes: {len(data['nodes'])}\n")
            f.write(f"Links: {len(data['links'])}\n")
            f.write(f"Stats: {data.get('stats')}\n")
            
            if len(data['nodes']) == 0:
                f.write("WARNING: No nodes returned!\n")
                # Check user count in DB
                count = db.execute_single("SELECT COUNT(*) as count FROM user")
                f.write(f"Total users in DB: {count['count']}\n")
                
                # Check if any user meets criteria
                users = db.execute_query("SELECT * FROM user LIMIT 5")
                f.write(f"Sample users: {json.dumps([dict(u) for u in users], default=str)}\n")
            else:
                 f.write(f"Sample node: {json.dumps(data['nodes'][0], default=str)}\n")

    except Exception as e:
        with open('network_debug.log', 'a', encoding='utf-8') as f:
            import traceback
            f.write(traceback.format_exc())

if __name__ == "__main__":
    test_network()
