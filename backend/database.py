import sqlite3
from pathlib import Path

DB_PATH = Path("lepka_backend.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        userId INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        passwordHash TEXT NOT NULL,
        nickname TEXT NOT NULL UNIQUE,
        roleName TEXT NOT NULL DEFAULT 'user',
        bioText TEXT NOT NULL DEFAULT '',
        ageCategory TEXT NOT NULL DEFAULT 'Взрослый 18+',
        favoriteColorsJson TEXT NOT NULL DEFAULT '[]',
        themeMode TEXT NOT NULL DEFAULT 'light',
        languageCode TEXT NOT NULL DEFAULT 'ru',
        notificationsEnabled INTEGER NOT NULL DEFAULT 1,
        isBlocked INTEGER NOT NULL DEFAULT 0,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        postId INTEGER PRIMARY KEY AUTOINCREMENT,
        userId INTEGER NOT NULL,
        titleText TEXT NOT NULL,
        descriptionText TEXT NOT NULL,
        categoryName TEXT NOT NULL,
        tagsText TEXT NOT NULL DEFAULT '',
        imagePath TEXT NOT NULL DEFAULT '',
        likesCount INTEGER NOT NULL DEFAULT 0,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS postComments (
        commentId INTEGER PRIMARY KEY AUTOINCREMENT,
        postId INTEGER NOT NULL,
        userId INTEGER NOT NULL,
        commentText TEXT NOT NULL,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (postId) REFERENCES posts(postId) ON DELETE CASCADE,
        FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS postLikes (
        likeId INTEGER PRIMARY KEY AUTOINCREMENT,
        postId INTEGER NOT NULL,
        userId INTEGER NOT NULL,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(postId, userId),
        FOREIGN KEY (postId) REFERENCES posts(postId) ON DELETE CASCADE,
        FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        projectId INTEGER PRIMARY KEY AUTOINCREMENT,
        userId INTEGER NOT NULL,
        projectName TEXT NOT NULL,
        categoryName TEXT NOT NULL,
        deadlineDate TEXT,
        descriptionText TEXT NOT NULL DEFAULT '',
        progressPercent REAL NOT NULL DEFAULT 0,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS projectSteps (
        stepId INTEGER PRIMARY KEY AUTOINCREMENT,
        projectId INTEGER NOT NULL,
        stepDescription TEXT NOT NULL,
        isCompleted INTEGER NOT NULL DEFAULT 0,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (projectId) REFERENCES projects(projectId) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS colorMixtures (
        mixtureId INTEGER PRIMARY KEY AUTOINCREMENT,
        userId INTEGER NOT NULL,
        mixtureName TEXT NOT NULL,
        resultHex TEXT NOT NULL,
        totalWeight REAL NOT NULL,
        recipeJson TEXT NOT NULL,
        createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (userId) REFERENCES users(userId) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()