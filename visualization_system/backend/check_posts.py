#!/usr/bin/env python
"""Check database post counts"""
import sys
sys.path.append('.')

from database.db_manager import get_db_manager

db = get_db_manager()
print(f"Total posts: {db.execute_single('SELECT COUNT(*) as cnt FROM post')['cnt']}")
print(f"Original posts: {db.execute_single('SELECT COUNT(*) as cnt FROM post WHERE original_post_id IS NULL')['cnt']}")
print(f"Reposts: {db.execute_single('SELECT COUNT(*) as cnt FROM post WHERE original_post_id IS NOT NULL')['cnt']}")
print(f"Comments: {db.execute_single('SELECT COUNT(*) as cnt FROM comment')['cnt']}")
