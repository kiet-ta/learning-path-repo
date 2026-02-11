"""
Database Connection - Infrastructure Layer
Manages SQLite connections with connection pooling and transaction support
"""
import sqlite3
import threading
from typing import Optional, ContextManager
from pathlib import Path
import logging
from contextlib import contextmanager

from .schema import DatabaseSchema


class DatabaseConnection:
    """
    SQLite database connection manager with transaction support
    Thread-safe connection management for concurrent operations
    """
    
    def __init__(self, db_path: Path, logger: Optional[logging.Logger] = None):
        """
        Initialize database connection manager
        
        Args:
            db_path: Path to SQLite database file
            logger: Optional logger instance
        """
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self._local = threading.local()
        
        # Ensure database directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize database with schema and indexes"""
        try:
            with self.get_connection() as conn:
                current_version = DatabaseSchema.get_schema_version(conn)
                
                if current_version < DatabaseSchema.SCHEMA_VERSION:
                    self.logger.info(f"Upgrading database schema from v{current_version} to v{DatabaseSchema.SCHEMA_VERSION}")
                    DatabaseSchema.setup_database(conn)
                    self.logger.info("Database schema upgrade completed")
                else:
                    self.logger.debug("Database schema is up to date")
                    
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection
        
        Returns:
            SQLite connection for current thread
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0  # 30 second timeout
            )
            
            # Configure connection
            self._local.connection.row_factory = sqlite3.Row  # Dict-like access
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            
        return self._local.connection
    
    @contextmanager
    def transaction(self) -> ContextManager[sqlite3.Connection]:
        """
        Context manager for database transactions
        Automatically commits on success, rolls back on error
        
        Returns:
            Database connection within transaction context
        """
        conn = self.get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Transaction rolled back due to error: {e}")
            raise
    
    @contextmanager
    def cursor(self) -> ContextManager[sqlite3.Cursor]:
        """
        Context manager for database cursor
        
        Returns:
            Database cursor
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query and return cursor
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Cursor with query results
        """
        conn = self.get_connection()
        return conn.execute(query, params)
    
    def execute_many(self, query: str, params_list: list) -> None:
        """
        Execute query with multiple parameter sets (batch insert)
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        with self.transaction() as conn:
            conn.executemany(query, params_list)
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Fetch single row from query
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Single row or None
        """
        cursor = self.execute_query(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """
        Fetch all rows from query
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of rows
        """
        cursor = self.execute_query(query, params)
        return cursor.fetchall()
    
    def get_last_insert_id(self) -> int:
        """Get last inserted row ID"""
        conn = self.get_connection()
        return conn.lastrowid
    
    def close(self) -> None:
        """Close database connection"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def vacuum(self) -> None:
        """Optimize database by running VACUUM"""
        try:
            conn = self.get_connection()
            conn.execute("VACUUM")
            self.logger.info("Database vacuum completed")
        except Exception as e:
            self.logger.error(f"Database vacuum failed: {e}")
    
    def get_database_stats(self) -> dict:
        """Get database statistics"""
        stats = {}
        
        try:
            # Get table row counts
            tables = [
                'repositories', 'topics', 'repository_topics', 
                'dependencies', 'learning_paths', 'learning_path_nodes',
                'progress_records', 'overrides'
            ]
            
            for table in tables:
                count = self.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                stats[f"{table}_count"] = count['count'] if count else 0
            
            # Get database size
            size_result = self.fetch_one("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            stats['database_size_bytes'] = size_result['size'] if size_result else 0
            
            # Get index usage
            index_result = self.fetch_all("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
            stats['index_count'] = len(index_result)
            
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
            
        return stats


class DatabaseFactory:
    """
    Factory for creating database connections
    Follows Singleton pattern for connection management
    """
    
    _instances = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_connection(cls, db_path: Path, logger: Optional[logging.Logger] = None) -> DatabaseConnection:
        """
        Get or create database connection instance
        
        Args:
            db_path: Path to database file
            logger: Optional logger
            
        Returns:
            DatabaseConnection instance
        """
        db_key = str(db_path.absolute())
        
        if db_key not in cls._instances:
            with cls._lock:
                if db_key not in cls._instances:
                    cls._instances[db_key] = DatabaseConnection(db_path, logger)
        
        return cls._instances[db_key]
    
    @classmethod
    def close_all(cls) -> None:
        """Close all database connections"""
        with cls._lock:
            for connection in cls._instances.values():
                connection.close()
            cls._instances.clear()
