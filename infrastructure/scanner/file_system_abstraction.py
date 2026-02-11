"""
File System Abstraction - Infrastructure Layer
Provides abstraction over file system operations for testability and flexibility
"""
from abc import ABC, abstractmethod
from typing import List, Iterator, Optional, Tuple
from pathlib import Path
import asyncio
import aiofiles
import os


class FileSystemInterface(ABC):
    """
    Abstract interface for file system operations
    Follows Dependency Inversion Principle - high-level modules depend on abstraction
    """
    
    @abstractmethod
    async def exists(self, path: Path) -> bool:
        """Check if path exists"""
        pass
    
    @abstractmethod
    async def is_directory(self, path: Path) -> bool:
        """Check if path is a directory"""
        pass
    
    @abstractmethod
    async def is_file(self, path: Path) -> bool:
        """Check if path is a file"""
        pass
    
    @abstractmethod
    async def list_directory(self, path: Path) -> List[Path]:
        """List directory contents"""
        pass
    
    @abstractmethod
    async def read_file(self, path: Path, max_size_bytes: int = None) -> str:
        """Read file content with optional size limit"""
        pass
    
    @abstractmethod
    async def get_file_size(self, path: Path) -> int:
        """Get file size in bytes"""
        pass
    
    @abstractmethod
    async def walk_directory(self, path: Path, max_depth: int = None) -> Iterator[Tuple[Path, List[Path], List[Path]]]:
        """Walk directory tree (path, dirs, files)"""
        pass


class AsyncFileSystem(FileSystemInterface):
    """
    Async file system implementation
    Follows Single Responsibility - only file system operations
    """
    
    async def exists(self, path: Path) -> bool:
        """Check if path exists"""
        return path.exists()
    
    async def is_directory(self, path: Path) -> bool:
        """Check if path is a directory"""
        return path.is_dir()
    
    async def is_file(self, path: Path) -> bool:
        """Check if path is a file"""
        return path.is_file()
    
    async def list_directory(self, path: Path) -> List[Path]:
        """List directory contents"""
        try:
            return [item for item in path.iterdir()]
        except (OSError, PermissionError):
            return []
    
    async def read_file(self, path: Path, max_size_bytes: int = None) -> str:
        """Read file content with optional size limit"""
        try:
            # Check file size first if limit specified
            if max_size_bytes:
                file_size = await self.get_file_size(path)
                if file_size > max_size_bytes:
                    raise ValueError(f"File {path} too large: {file_size} bytes")
            
            async with aiofiles.open(path, 'r', encoding='utf-8', errors='ignore') as f:
                if max_size_bytes:
                    content = await f.read(max_size_bytes)
                else:
                    content = await f.read()
                return content
        except (OSError, PermissionError, UnicodeDecodeError) as e:
            raise IOError(f"Cannot read file {path}: {e}")
    
    async def get_file_size(self, path: Path) -> int:
        """Get file size in bytes"""
        try:
            return path.stat().st_size
        except (OSError, PermissionError):
            return 0
    
    async def walk_directory(self, path: Path, max_depth: int = None) -> Iterator[Tuple[Path, List[Path], List[Path]]]:
        """Walk directory tree (path, dirs, files)"""
        async def _walk_recursive(current_path: Path, current_depth: int = 0):
            if max_depth is not None and current_depth > max_depth:
                return
            
            try:
                items = await self.list_directory(current_path)
                dirs = []
                files = []
                
                for item in items:
                    if await self.is_directory(item):
                        dirs.append(item)
                    elif await self.is_file(item):
                        files.append(item)
                
                yield (current_path, dirs, files)
                
                # Recursively walk subdirectories
                for dir_path in dirs:
                    async for result in _walk_recursive(dir_path, current_depth + 1):
                        yield result
                        
            except (OSError, PermissionError):
                # Skip directories we can't access
                yield (current_path, [], [])
        
        async for result in _walk_recursive(path):
            yield result


class MockFileSystem(FileSystemInterface):
    """
    Mock file system for testing
    Follows Liskov Substitution Principle - can replace real file system
    """
    
    def __init__(self):
        self.files = {}  # path -> content
        self.directories = set()
    
    def add_file(self, path: str, content: str):
        """Add a mock file"""
        self.files[Path(path)] = content
    
    def add_directory(self, path: str):
        """Add a mock directory"""
        self.directories.add(Path(path))
    
    async def exists(self, path: Path) -> bool:
        return path in self.files or path in self.directories
    
    async def is_directory(self, path: Path) -> bool:
        return path in self.directories
    
    async def is_file(self, path: Path) -> bool:
        return path in self.files
    
    async def list_directory(self, path: Path) -> List[Path]:
        items = []
        for file_path in self.files:
            if file_path.parent == path:
                items.append(file_path)
        for dir_path in self.directories:
            if dir_path.parent == path:
                items.append(dir_path)
        return items
    
    async def read_file(self, path: Path, max_size_bytes: int = None) -> str:
        if path not in self.files:
            raise IOError(f"File not found: {path}")
        content = self.files[path]
        if max_size_bytes and len(content) > max_size_bytes:
            return content[:max_size_bytes]
        return content
    
    async def get_file_size(self, path: Path) -> int:
        if path not in self.files:
            return 0
        return len(self.files[path])
    
    async def walk_directory(self, path: Path, max_depth: int = None) -> Iterator[Tuple[Path, List[Path], List[Path]]]:
        # Simplified mock implementation
        dirs = [d for d in self.directories if d.parent == path]
        files = [f for f in self.files if f.parent == path]
        yield (path, dirs, files)
