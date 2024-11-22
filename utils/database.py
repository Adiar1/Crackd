import sqlite3
import os
import logging

DATABASE_NAME = 'sat_bot.db'
logger = logging.getLogger(__name__)


def init_db():
    db_path = os.path.abspath(DATABASE_NAME)
    logger.info(f"Initializing database at {db_path}")

    try:
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()

        # Questions table - updated with separate option columns
        c.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                question TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                explanation TEXT,
                difficulty TEXT CHECK(difficulty IN ('easy', 'medium', 'hard')),
                domain TEXT,
                skill TEXT,
                image_url TEXT
            )
        ''')

        # Archived questions table - updated with separate option columns
        c.execute('''
            CREATE TABLE IF NOT EXISTS question_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                question TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                explanation TEXT,
                difficulty TEXT CHECK(difficulty IN ('easy', 'medium', 'hard')),
                domain TEXT,
                skill TEXT,
                image_url TEXT,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # User stats table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER NOT NULL,
                total_correct INTEGER NOT NULL DEFAULT 0,
                total_attempts INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id)
            )
        ''')

        # User skill-level stats table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_skill_stats (
                user_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                skill TEXT NOT NULL,
                total_correct INTEGER NOT NULL DEFAULT 0,
                total_attempts INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, question_type, domain, skill)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database and tables created successfully.")
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")


def get_database_connection():
    return sqlite3.connect(DATABASE_NAME)


def archive_question(question_id):
    """
    Move a question from the questions table to the question_archives table,
    preserving the original question ID and handling multiple archive attempts
    """
    try:
        conn = get_database_connection()
        c = conn.cursor()

        # Check if the question is already in archives
        c.execute("SELECT id FROM question_archives WHERE id = ?", (question_id,))
        if c.fetchone():
            # Question already archived
            return False

        # Get the full question data
        c.execute("""
            SELECT type, question, correct_answer, option_a, option_b, option_c, option_d, 
                   explanation, difficulty, domain, skill, image_url
            FROM questions 
            WHERE id = ?
        """, (question_id,))
        question_data = c.fetchone()

        if question_data:
            # Insert into archives with the SAME id
            c.execute("""
                INSERT INTO question_archives 
                (id, type, question, correct_answer, option_a, option_b, option_c, option_d, 
                 explanation, difficulty, domain, skill, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (question_id,) + question_data)

            # Delete from questions
            c.execute("DELETE FROM questions WHERE id = ?", (question_id,))

            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Error archiving question: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()