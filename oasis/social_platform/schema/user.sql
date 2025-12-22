-- This is the schema definition for the user table
CREATE TABLE user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER,
    user_name TEXT,
    name TEXT,
    bio TEXT,
    created_at DATETIME,
    num_followings INTEGER DEFAULT 0,
    num_followers INTEGER DEFAULT 0,
    follower_list TEXT DEFAULT '',
    follower_id_list TEXT DEFAULT '',
    follower_num_list TEXT DEFAULT '',
    weibo_id TEXT DEFAULT ''
);
