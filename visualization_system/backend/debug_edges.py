
import sys
import os
import json

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import get_db_manager
from utils.data_aggregation import build_relationship_network

def debug_edges():
    try:
        db = get_db_manager()
        print(f"Connected to DB: {db.db_path}")
        
        # 1. Find a user with followers
        target_user = db.execute_single("SELECT * FROM user WHERE num_followers > 0 LIMIT 1")
        
        if not target_user:
            print("No users with followers found.")
            return

        print(f"Target User: {target_user['name']} (ID: {target_user['user_id']}) - Followers: {target_user['num_followers']}")
        
        # 2. Check follow table
        followers = db.execute_query(f"SELECT * FROM follow WHERE followee_id = {target_user['user_id']}")
        print(f"Actual follow records found: {len(followers)}")
        for f in followers:
            print(f"  - Follower ID: {f['follower_id']}")
            
            # Check if follower exists in user table
            follower_exists = db.execute_single(f"SELECT * FROM user WHERE user_id = {f['follower_id']}")
            print(f"    -> Exists in User table: {bool(follower_exists)}")

        # 3. different limits check
        print("\nChecking build_relationship_network with limit=2000...")
        data = build_relationship_network(db, limit=2000, min_followers=0)
        
        # Check if target user and follower are in nodes
        node_ids = {n['user_id']: n for n in data['nodes']}
        
        target_in_nodes = target_user['user_id'] in node_ids
        print(f"Target User in Nodes: {target_in_nodes}")
        
        for f in followers:
            follower_in_nodes = f['follower_id'] in node_ids
            print(f"Follower {f['follower_id']} in Nodes: {follower_in_nodes}")
            
            # Check for link
            link_found = False
            expected_source = f"U_{f['follower_id']}"
            expected_target = f"U_{target_user['user_id']}"
            
            for link in data['links']:
                if link['source'] == expected_source and link['target'] == expected_target:
                    link_found = True
                    break
            
            print(f"Link {expected_source} -> {expected_target} found: {link_found}")

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_edges()
