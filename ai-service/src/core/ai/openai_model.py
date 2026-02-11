"""
OpenAI Model - AI Core Layer
OpenAI GPT model implementation with rate limiting and error handling
"""
import asyncio
import openai
from typing import Dict, List, Any, Optional
import time
import logging
from datetime import datetime, timedelta

from .base_model import BaseAIModel, ModelRequest, ModelResponse, ModelType, ModelCapabilities, ModelMetrics

class OpenAIModel(BaseAIModel):
    """
    OpenAI GPT model implementation
    Supports GPT-3.5, GPT-4, and future OpenAI models
    """
    
    def __init__(self, model_name: str, config: Dict[str, Any]):
        """
        Initialize OpenAI model
        
        Args:
            model_name: OpenAI model name (gpt-3.5-turbo, gpt-4, etc.)
            config: Configuration including API key, rate limits, etc.
        """
        super().__init__(model_name, ModelType.OPENAI_GPT, config)
        
        self.api_key = config.get('api_key')
        self.organization = config.get('organization')
        self.rate_limit_rpm = config.get('rate_limit_rpm', 60)  # Requests per minute
        self.rate_limit_tpm = config.get('rate_limit_tpm', 90000)  # Tokens per minute
        
        # Rate limiting tracking
        self.request_timestamps = []
        self.token_usage_timestamps = []
        
        # Model capabilities
        self.capabilities = ModelCapabilities()
        self._set_model_capabilities()
        
        # Metrics
        self.metrics = ModelMetrics()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
    def _set_model_capabilities(self):
        """Set model-specific capabilities"""
        if 'gpt-4' in self.model_name:
            self.capabilities.max_context_length = 8192
            self.capabilities.supports_function_calling = True
        elif 'gpt-3.5-turbo' in self.model_name:
            self.capabilities.max_context_length = 4096
            self.capabilities.supports_function_calling = True
        
        self.capabilities.supports_streaming = True
        self.capabilities.deterministic = True  # With low temperature
    
    async def initialize(self) -> bool:
        """
        Initialize OpenAI client
        
        Returns:
            True if initialization successful
        """
        try:
            if not self.api_key:
                raise ValueError("OpenAI API key not provided")
            
            # Set OpenAI configuration
            openai.api_key = self.api_key
            if self.organization:
                openai.organization = self.organization
            
            # Test connection with a simple request
            await self._test_connection()
            
            self.is_initialized = True
            self.logger.info(f"OpenAI model {self.model_name} initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI model: {e}")
            return False
    
    async def _test_connection(self):
        """Test OpenAI API connection"""
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
                temperature=0
            )
            return True
        except Exception as e:
            raise Exception(f"OpenAI API connection test failed: {e}")
    
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """
        Generate response using OpenAI model
        
        Args:
            request: Standardized model request
            
        Returns:
            Standardized model response
        """
        start_time = time.time()
        
        try:
            # Validate request
            if not self.validate_request(request):
                raise ValueError("Invalid request parameters")
            
            # Check rate limits
            await self._check_rate_limits(request)
            
            # Prepare messages
            messages = self._prepare_messages(request)
            
            # Make API call
            response = await openai.ChatCompletion.acreate(
                model=self.model_name,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                timeout=request.timeout
            )
            
            # Extract response data
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Calculate confidence (simple heuristic for now)
            confidence = self._calculate_confidence(response, request)
            
            # Generate explanation
            explanation = self._generate_explanation(response, request)
            
            processing_time = time.time() - start_time
            
            # Record metrics
            self.metrics.record_request(
                success=True,
                response_time=processing_time,
                tokens_used=tokens_used,
                cost=self._calculate_cost(tokens_used)
            )
            
            return self.create_response(
                content=content,
                confidence=confidence,
                explanation=explanation,
                processing_time=processing_time,
                tokens_used=tokens_used,
                metadata={
                    'model': response.model,
                    'finish_reason': response.choices[0].finish_reason,
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.metrics.record_request(success=False, response_time=processing_time)
            
            self.logger.error(f"OpenAI generation failed: {e}")
            
            # Return error response
            return self.create_response(
                content="",
                confidence=0.0,
                explanation=f"Generation failed: {str(e)}",
                processing_time=processing_time,
                metadata={'error': str(e)}
            )
    
    def _prepare_messages(self, request: ModelRequest) -> List[Dict[str, str]]:
        """
        Prepare messages for OpenAI API
        
        Args:
            request: Model request
            
        Returns:
            List of message dictionaries
        """
        messages = []
        
        # Add system message if context provided
        if 'system_prompt' in request.context:
            messages.append({
                "role": "system",
                "content": request.context['system_prompt']
            })
        
        # Add user message
        messages.append({
            "role": "user", 
            "content": request.prompt
        })
        
        return messages
    
    async def _check_rate_limits(self, request: ModelRequest):
        """
        Check and enforce rate limits
        
        Args:
            request: Model request
        """
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old timestamps
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > minute_ago]
        
        # Check request rate limit
        if len(self.request_timestamps) >= self.rate_limit_rpm:
            sleep_time = 60 - (now - self.request_timestamps[0]).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        # Record current request
        self.request_timestamps.append(now)
    
    def _calculate_confidence(self, response, request: ModelRequest) -> float:
        """
        Calculate confidence score for the response
        
        Args:
            response: OpenAI API response
            request: Original request
            
        Returns:
            Confidence score (0-1)
        """
        # Simple heuristic based on finish reason and temperature
        base_confidence = 0.8
        
        if response.choices[0].finish_reason == 'stop':
            base_confidence += 0.1
        elif response.choices[0].finish_reason == 'length':
            base_confidence -= 0.2
        
        # Lower confidence for higher temperature
        temperature_penalty = request.temperature * 0.2
        
        return max(0.0, min(1.0, base_confidence - temperature_penalty))
    
    def _generate_explanation(self, response, request: ModelRequest) -> str:
        """
        Generate explanation for the response
        
        Args:
            response: OpenAI API response
            request: Original request
            
        Returns:
            Explanation string
        """
        explanation_parts = [
            f"Generated using {self.model_name}",
            f"Temperature: {request.temperature}",
            f"Tokens used: {response.usage.total_tokens}",
            f"Finish reason: {response.choices[0].finish_reason}"
        ]
        
        return " | ".join(explanation_parts)
    
    def _calculate_cost(self, tokens_used: int) -> float:
        """
        Calculate estimated cost for the request
        
        Args:
            tokens_used: Number of tokens used
            
        Returns:
            Estimated cost in USD
        """
        # Simplified cost calculation (update with actual pricing)
        if 'gpt-4' in self.model_name:
            cost_per_1k_tokens = 0.03
        elif 'gpt-3.5-turbo' in self.model_name:
            cost_per_1k_tokens = 0.002
        else:
            cost_per_1k_tokens = 0.002
        
        return (tokens_used / 1000) * cost_per_1k_tokens
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check OpenAI model health
        
        Returns:
            Health status information
        """
        try:
            # Simple health check with minimal token usage
            start_time = time.time()
            
            response = await openai.ChatCompletion.acreate(
                model=self.model_name,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0
            )
            
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'model': self.model_name,
                'response_time': response_time,
                'is_initialized': self.is_initialized,
                'metrics': {
                    'total_requests': self.metrics.total_requests,
                    'success_rate': self.metrics.get_success_rate(),
                    'average_response_time': self.metrics.average_response_time,
                    'total_tokens_used': self.metrics.total_tokens_used,
                    'total_cost': self.metrics.total_cost
                }
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'model': self.model_name,
                'error': str(e),
                'is_initialized': self.is_initialized
            }
