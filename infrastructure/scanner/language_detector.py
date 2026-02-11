"""
Language Detector - Infrastructure Layer
Detects primary programming language from file extensions and content
"""
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from collections import Counter
import re

from .scanner_config import ScannerConfig
from .file_system_abstraction import FileSystemInterface
from ..logging.structured_logger import StructuredLogger


class LanguageDetector:
    """
    Detects programming language from repository files
    Follows Single Responsibility - only language detection logic
    """
    
    def __init__(self, config: ScannerConfig, file_system: FileSystemInterface, logger: StructuredLogger):
        """
        Initialize language detector
        
        Args:
            config: Scanner configuration
            file_system: File system abstraction
            logger: Structured logger
        """
        self.config = config
        self.file_system = file_system
        self.logger = logger
    
    async def detect_primary_language(self, repo_path: Path) -> Tuple[str, Dict[str, int]]:
        """
        Detect primary programming language and distribution
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Tuple of (primary_language, language_distribution)
        """
        language_counts = Counter()
        total_files = 0
        
        try:
            # Walk through repository files
            async for current_path, dirs, files in self.file_system.walk_directory(repo_path, max_depth=10):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if not self.config.should_ignore_directory(d.name)]
                
                for file_path in files:
                    # Skip binary files
                    if self.config.is_binary_file(file_path):
                        continue
                    
                    # Skip large files
                    try:
                        file_size = await self.file_system.get_file_size(file_path)
                        if file_size > self.config.max_file_size_mb * 1024 * 1024:
                            continue
                    except:
                        continue
                    
                    # Detect language from extension
                    language = self._detect_language_from_file(file_path)
                    if language != 'unknown':
                        language_counts[language] += 1
                        total_files += 1
            
            # Determine primary language
            if not language_counts:
                return 'unknown', {}
            
            # Convert to percentages and find primary
            language_distribution = dict(language_counts)
            primary_language = language_counts.most_common(1)[0][0]
            
            self.logger.log_language_detection(
                str(repo_path), 
                primary_language, 
                language_distribution
            )
            
            return primary_language, language_distribution
            
        except Exception as e:
            self.logger.error(f"Error detecting language for {repo_path}", error=e)
            return 'unknown', {}
    
    def _detect_language_from_file(self, file_path: Path) -> str:
        """
        Detect language from file path and name
        
        Args:
            file_path: Path to file
            
        Returns:
            Detected language or 'unknown'
        """
        # Check extension first
        extension = file_path.suffix.lower()
        language = self.config.get_language_from_extension(extension)
        
        if language != 'unknown':
            return language
        
        # Special cases based on filename
        filename = file_path.name.lower()
        
        # Docker files
        if filename in ['dockerfile', 'dockerfile.dev', 'dockerfile.prod']:
            return 'dockerfile'
        
        # Makefile
        if filename in ['makefile', 'makefile.am', 'makefile.in']:
            return 'makefile'
        
        # CMake
        if filename in ['cmakelists.txt'] or filename.startswith('cmake'):
            return 'cmake'
        
        # Configuration files
        if filename.endswith('.conf') or filename.endswith('.config'):
            return 'config'
        
        # Shell scripts without extension
        if self._is_shell_script(file_path):
            return 'shell'
        
        return 'unknown'
    
    def _is_shell_script(self, file_path: Path) -> bool:
        """
        Check if file is a shell script by examining shebang
        
        Args:
            file_path: Path to file
            
        Returns:
            True if appears to be shell script
        """
        try:
            # This is a simplified check - in real implementation,
            # you might want to read the first line to check for shebang
            filename = file_path.name.lower()
            return any(filename.startswith(prefix) for prefix in ['run', 'start', 'build', 'deploy', 'install'])
        except:
            return False
    
    async def get_language_statistics(self, repo_path: Path) -> Dict[str, any]:
        """
        Get detailed language statistics
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Dictionary with language statistics
        """
        primary_language, distribution = await self.detect_primary_language(repo_path)
        
        total_files = sum(distribution.values())
        
        # Calculate percentages
        percentages = {}
        if total_files > 0:
            for lang, count in distribution.items():
                percentages[lang] = (count / total_files) * 100
        
        return {
            'primary_language': primary_language,
            'total_files': total_files,
            'language_distribution': distribution,
            'language_percentages': percentages,
            'languages_count': len(distribution)
        }
