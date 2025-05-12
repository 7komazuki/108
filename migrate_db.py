#!/usr/bin/env python3
import sqlite3
import os
import sys

def migrate_database():
    """
    Creates or updates the database schema for the game application.
    Takes a more direct approach to ensure columns are created properly.
    """
    # Paths to the database files
    users_db_path = os.path.join("instance", "users.db")
    
    print(f"Checking database at {users_db_path}...")
    
    # Check if directory exists
    if not os.path.exists("instance"):
        os.makedirs("instance")
        print("Created instance directory")
    
    # Connect to the database (will create if doesn't exist)
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    
    try:
        # Check if user table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if not cursor.fetchone():
            print("Creating user table...")
            cursor.execute('''
                CREATE TABLE user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(80) UNIQUE,
                    email VARCHAR(120) UNIQUE,
                    password VARCHAR(200),
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    games_played INTEGER DEFAULT 0,
                    favorite_cards VARCHAR(20) DEFAULT '8,8,8'
                )
            ''')
            print("User table created successfully!")
        else:
            # Check if stats and favorite cards columns exist
            cursor.execute("PRAGMA table_info(user)")
            columns = [column[1] for column in cursor.fetchall()]

            required_columns = [
                'id', 'username', 'email', 'password',
                'wins', 'losses', 'games_played', 'favorite_cards'
            ]

            # Check if any columns are missing
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                print(f"Missing columns in user table: {', '.join(missing_columns)}")

                # Add missing columns
                for column in missing_columns:
                    try:
                        if column == 'wins' or column == 'losses' or column == 'games_played':
                            cursor.execute(f"ALTER TABLE user ADD COLUMN {column} INTEGER DEFAULT 0")
                        elif column == 'favorite_cards':
                            cursor.execute(f"ALTER TABLE user ADD COLUMN {column} VARCHAR(20) DEFAULT '8,8,8'")
                        print(f"Added missing column: {column}")
                    except Exception as e:
                        print(f"Error adding column {column}: {e}")

                print("User table updated with new columns!")
        
        # Check if session_data table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_data'")
        if not cursor.fetchone():
            print("Creating session_data table with all required columns...")
            cursor.execute('''
                CREATE TABLE session_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_code VARCHAR(36) UNIQUE,
                    data TEXT,
                    description TEXT,
                    password TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_public BOOLEAN DEFAULT 1,
                    FOREIGN KEY (created_by) REFERENCES user(id)
                )
            ''')
            print("session_data table created successfully!")
        else:
            # The table exists, but we need to check if it has all required columns
            # Since SQLite doesn't fully support ALTER TABLE to add columns easily,
            # we'll recreate the table if needed
            
            # Get existing columns
            cursor.execute("PRAGMA table_info(session_data)")
            columns = [column[1] for column in cursor.fetchall()]
            
            required_columns = [
                'id', 'session_code', 'data', 'description', 
                'password', 'created_by', 'created_at', 'is_public'
            ]
            
            # Check if any columns are missing
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                print(f"Missing columns in session_data table: {', '.join(missing_columns)}")
                print("Recreating session_data table with all required columns...")
                
                # Backup existing data
                cursor.execute("SELECT session_code, data FROM session_data")
                existing_sessions = cursor.fetchall()
                
                # Drop existing table
                cursor.execute("DROP TABLE session_data")
                
                # Create new table with all columns
                cursor.execute('''
                    CREATE TABLE session_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_code VARCHAR(36) UNIQUE,
                        data TEXT,
                        description TEXT,
                        password TEXT,
                        created_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_public BOOLEAN DEFAULT 1,
                        FOREIGN KEY (created_by) REFERENCES user(id)
                    )
                ''')
                
                # Restore data
                for session_code, data in existing_sessions:
                    cursor.execute(
                        "INSERT INTO session_data (session_code, data) VALUES (?, ?)",
                        (session_code, data)
                    )
                
                print(f"Restored {len(existing_sessions)} existing sessions to new table structure.")
            else:
                print("session_data table has all required columns!")
        
        # Commit all changes
        conn.commit()
        print("Database schema is now up to date!")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting database migration...")
    success = migrate_database()
    if success:
        print("Database migration completed successfully!")
        sys.exit(0)
    else:
        print("Database migration failed!")
        sys.exit(1)