import sqlite3
import os

def get_db_connection(db_path='task_priority.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path='task_priority.db'):
    # Check if database already exists
    if os.path.exists(db_path):
        return

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Create Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create Tasks Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            deadline DATE NOT NULL,
            estimated_effort REAL NOT NULL,
            business_impact INTEGER NOT NULL,
            urgency INTEGER NOT NULL,
            dependency_count INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users (user_id)
        )
    ''')

    # Create Predictions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            priority_score REAL NOT NULL,
            priority_label TEXT NOT NULL,
            model_prediction TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES Tasks (task_id)
        )
    ''')

    # Create Batches Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Batches (
            batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            task_count INTEGER NOT NULL,
            result_filepath TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users (user_id)
        )
    ''')

    # Create Override History Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS OverrideHistory (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            original_priority TEXT NOT NULL,
            new_priority TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES Tasks (task_id)
        )
    ''')

    conn.commit()
    conn.close()
