"""
Base Model - AI Core Layer
Abstract base class for all AI models to ensure LLM-agnostic architecture
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import time
import hashlib
import json

class ModelType(Enum):
    """Supported model types"""
    OPENAI_GPT = "openai_gpt"
    LOCAL_LLM = "local_llm"
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"

@dataclass
class ModelResponse:
    """Standardized model response"""
    content: str
    confidence_score: float
    explanation: str
    model_version: str
    prompt_version: str
    processing_time: float
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    metadata: Dict[str, Any] = None

@dataclass
class ModelRequest:
    """Standardized model request"""
    prompt: str
    context: Dict[str, Any]
    temperature: float = 0.1  # Low for determinism
    max_tokens: Optional[int] = None
    timeout: float = 30.0
    cache_key: Optional[str] = None

class BaseAIModel(ABC):
    """
    Abstract base class for all AI models
    Ensures consistent interface across different LLM providers
    """
    
    def __init__(self, model_name: str, model_type: ModelType, config: Dict[str, Any]):
        """
        Initialize base model
        
        Args:
            model_name: Name/identifier of the model
            model_type: Type of model (GPT, local, etc.)
            config: Model-specific configuration
        """
        self.model_name = model_name
        self.model_type = model_type
        self.config = config
        self.version = config.get('version', '1.0.0')
        self.is_initialized = False
        
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the model (load weights, connect to API, etc.)
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """
        Generate response from model
        
        Args:
            request: Standardized model request
            
        Returns:
            Standardized model response
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check model health and availability
        
        Returns:
            Health status information
        """
        pass
    
    def generate_cache_key(self, request: ModelRequest) -> str:
        """
        Generate deterministic cache key for request
        
        Args:
            request: Model request
            
        Returns:
            Cache key string
        """
        if request.cache_key:
            return request.cache_key
            
        # Create deterministic hash from request content
        content = {
            'prompt': request.prompt,
            'context': request.context,
            'temperature': request.temperature,
            'model_name': self.model_name,
            'model_version': self.version
        }
        
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def validate_request(self, request: ModelRequest) -> bool:
        """
        Validate model request
        
        Args:
            request: Model request to validate
            
        Returns:
            True if request is valid
        """
        if not request.prompt or not request.prompt.strip():
            return False
            
        if request.temperature < 0 or request.temperature > 2:
            return False
            
        if request.max_tokens and request.max_tokens <= 0:
            return False
            
        return True
    
    def create_response(self, content: str, confidence: float, 
                       explanation: str, processing_time: float,
                       tokens_used: Optional[int] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """
        Create standardized model response
        
        Args:
            content: Generated content
            confidence: Confidence score (0-1)
            explanation: Explanation of the result
            processing_time: Time taken to process
            tokens_used: Number of tokens used
            metadata: Additional metadata
            
        Returns:
            Standardized model response
        """
        return ModelResponse(
            content=content,
            confidence_score=confidence,
            explanation=explanation,
            model_version=self.version,
            prompt_version=self.config.get('prompt_version', '1.0.0'),
            processing_time=processing_time,
            tokens_used=tokens_used,
            metadata=metadata or {}
        )

class ModelCapabilities:
    """Model capability flags"""
    
    def __init__(self):
        self.supports_streaming = False
        self.supports_function_calling = False
        self.supports_embeddings = False
        self.supports_fine_tuning = False
        self.max_context_length = 4096
        self.supports_batch_processing = False
        self.deterministic = True
        
class ModelMetrics:
    """Model performance metrics"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.average_response_time = 0.0
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.cache_hit_rate = 0.0
        
    def record_request(self, success: bool, response_time: float, 
                      tokens_used: int = 0, cost: float = 0.0):
        """Record request metrics"""
        self.total_requests += 1
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            
        # Update average response time
        self.average_response_time = (
            (self.average_response_time * (self.total_requests - 1) + response_time) 
            / self.total_requests
        )
        
        self.total_tokens_used += tokens_used
        self.total_cost += cost
    
    def get_success_rate(self) -> float:
        """Get success rate percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
