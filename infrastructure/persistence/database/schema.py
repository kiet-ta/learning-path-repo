"""
Database Schema - Infrastructure Layer
Normalized SQLite schema for Auto Learning Path Generator
"""
import sqlite3
from typing import Optional
from pathlib import Path
import logging

class DatabaseSchema:
    """
    Database schema management for learning path generator
    Follows normalized design with proper indexing for 500+ repositories
    """
    
    # Schema version for migrations
    SCHEMA_VERSION = 1
    
    @staticmethod
    def create_tables(connection: sqlite3.Connection) -> None:
        """
        Create all database tables with proper constraints and indexes
        
        Args:
            connection: SQLite database connection
        """
        cursor = connection.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create repositories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                primary_language TEXT NOT NULL,
                description TEXT,
                content_hash TEXT NOT NULL,
                skill_type TEXT,
                skill_level TEXT,
                complexity_score REAL DEFAULT 0.0,
                estimated_hours INTEGER DEFAULT 0,
                lines_of_code INTEGER DEFAULT 0,
                file_count INTEGER DEFAULT 0,
                last_analyzed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create topics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                description TEXT,
                difficulty_weight REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create repository_topics junction table (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repository_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id TEXT NOT NULL,
                topic_id INTEGER NOT NULL,
                relevance_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
                UNIQUE(repository_id, topic_id)
            )
        """)
        
        # Create dependencies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_repo_id TEXT NOT NULL,
                target_repo_id TEXT NOT NULL,
                dependency_type TEXT NOT NULL DEFAULT 'prerequisite',
                strength TEXT NOT NULL DEFAULT 'moderate',
                confidence_score REAL DEFAULT 1.0,
                created_by TEXT DEFAULT 'system',
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                FOREIGN KEY (target_repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(source_repo_id, target_repo_id),
                CHECK (source_repo_id != target_repo_id),
                CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
            )
        """)
        
        # Create learning_paths table (versioned)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                learner_id TEXT,
                name TEXT NOT NULL,
                description TEXT,
                total_estimated_hours INTEGER DEFAULT 0,
                total_repositories INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_optimized_at TIMESTAMP,
                UNIQUE(learner_id, version)
            )
        """)
        
        # Create learning_path_nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_path_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learning_path_id INTEGER NOT NULL,
                repository_id TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                milestone TEXT,
                estimated_hours INTEGER DEFAULT 0,
                is_overridden BOOLEAN DEFAULT FALSE,
                override_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (learning_path_id) REFERENCES learning_paths(id) ON DELETE CASCADE,
                FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(learning_path_id, repository_id),
                UNIQUE(learning_path_id, order_index)
            )
        """)
        
        # Create progress_records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id TEXT NOT NULL,
                learner_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'not_started',
                progress_percentage REAL DEFAULT 0.0,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                last_activity_at TIMESTAMP,
                total_time_minutes INTEGER DEFAULT 0,
                difficulty_rating INTEGER,
                satisfaction_rating INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(repository_id, learner_id),
                CHECK (progress_percentage >= 0.0 AND progress_percentage <= 100.0),
                CHECK (difficulty_rating IS NULL OR (difficulty_rating >= 1 AND difficulty_rating <= 5)),
                CHECK (satisfaction_rating IS NULL OR (satisfaction_rating >= 1 AND satisfaction_rating <= 5))
            )
        """)
        
        # Create overrides table (user customizations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id TEXT NOT NULL,
                learner_id TEXT NOT NULL,
                override_type TEXT NOT NULL,
                custom_order_index INTEGER,
                custom_milestone TEXT,
                custom_skill_level TEXT,
                custom_estimated_hours INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(repository_id, learner_id, override_type)
            )
        """)
        
        # Create metadata table for schema versioning
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert schema version
        cursor.execute("""
            INSERT OR REPLACE INTO schema_metadata (key, value) 
            VALUES ('schema_version', ?)
        """, (str(DatabaseSchema.SCHEMA_VERSION),))
        
        connection.commit()
    
    @staticmethod
    def create_indexes(connection: sqlite3.Connection) -> None:
        """
        Create performance indexes for 500+ repositories
        
        Args:
            connection: SQLite database connection
        """
        cursor = connection.cursor()
        
        # Repository indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_name ON repositories(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_content_hash ON repositories(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_skill_type ON repositories(skill_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_skill_level ON repositories(skill_level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_last_analyzed ON repositories(last_analyzed_at)")
        
        # Topic indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_name ON topics(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_category ON topics(category)")
        
        # Repository-topics indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repo_topics_repo_id ON repository_topics(repository_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repo_topics_topic_id ON repository_topics(topic_id)")
        
        # Dependencies indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_source ON dependencies(source_repo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_target ON dependencies(target_repo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_type ON dependencies(dependency_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_strength ON dependencies(strength)")
        
        # Learning path indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_paths_learner ON learning_paths(learner_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_paths_version ON learning_paths(version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_paths_status ON learning_paths(status)")
        
        # Learning path nodes indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_path_nodes_path_id ON learning_path_nodes(learning_path_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_path_nodes_repo_id ON learning_path_nodes(repository_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_path_nodes_order ON learning_path_nodes(order_index)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_path_nodes_milestone ON learning_path_nodes(milestone)")
        
        # Progress records indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_repo_id ON progress_records(repository_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_learner_id ON progress_records(learner_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_status ON progress_records(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_last_activity ON progress_records(last_activity_at)")
        
        # Overrides indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_overrides_repo_id ON overrides(repository_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_overrides_learner_id ON overrides(learner_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_overrides_type ON overrides(override_type)")
        
        connection.commit()
    
    @staticmethod
    def get_schema_version(connection: sqlite3.Connection) -> int:
        """Get current schema version"""
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT value FROM schema_metadata WHERE key = 'schema_version'")
            result = cursor.fetchone()
            return int(result[0]) if result else 0
        except sqlite3.OperationalError:
            return 0
    
    @staticmethod
    def setup_database(connection: sqlite3.Connection) -> None:
        """
        Complete database setup with tables and indexes
        
        Args:
            connection: SQLite database connection
        """
        DatabaseSchema.create_tables(connection)
        DatabaseSchema.create_indexes(connection)
        
        # Optimize SQLite for performance
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
        cursor.execute("PRAGMA synchronous = NORMAL")  # Balance safety/performance
        cursor.execute("PRAGMA cache_size = 10000")  # 10MB cache
        cursor.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp tables
        cursor.execute("PRAGMA mmap_size = 268435456")  # 256MB memory mapping
        
        connection.commit()
