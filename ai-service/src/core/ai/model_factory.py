"""
Model Factory - AI Core Layer
Factory pattern for creating and managing AI models
"""
from typing import Dict, Any, Optional
from enum import Enum
import logging

from .base_model import BaseAIModel, ModelType
from .openai_model import OpenAIModel
from .local_model import LocalLLMModel
from .embedding_model import EmbeddingModel

class ModelProvider(Enum):
    """Supported model providers"""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"

class ModelFactory:
    """
    Factory for creating AI models
    Supports multiple providers and model types
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._model_registry = {}
        self._initialized_models = {}
    
    def register_model(self, provider: ModelProvider, model_type: ModelType, 
                      model_class: type):
        """
        Register a model class for a provider and type
        
        Args:
            provider: Model provider
            model_type: Type of model
            model_class: Model class to register
        """
        key = (provider, model_type)
        self._model_registry[key] = model_class
        self.logger.info(f"Registered {model_class.__name__} for {provider.value}/{model_type.value}")
    
    async def create_model(self, provider: ModelProvider, model_type: ModelType,
                          model_name: str, config: Dict[str, Any]) -> BaseAIModel:
        """
        Create and initialize a model
        
        Args:
            provider: Model provider
            model_type: Type of model
            model_name: Name of the model
            config: Model configuration
            
        Returns:
            Initialized model instance
        """
        key = (provider, model_type)
        
        if key not in self._model_registry:
            raise ValueError(f"No model registered for {provider.value}/{model_type.value}")
        
        model_class = self._model_registry[key]
        
        try:
            # Create model instance
            model = model_class(model_name, config)
            
            # Initialize model
            success = await model.initialize()
            if not success:
                raise Exception("Model initialization failed")
            
            # Cache initialized model
            model_id = f"{provider.value}_{model_type.value}_{model_name}"
            self._initialized_models[model_id] = model
            
            self.logger.info(f"Created and initialized model: {model_id}")
            return model
            
        except Exception as e:
            self.logger.error(f"Failed to create model {model_name}: {e}")
            raise
    
    def get_model(self, provider: ModelProvider, model_type: ModelType,
                  model_name: str) -> Optional[BaseAIModel]:
        """
        Get an already initialized model
        
        Args:
            provider: Model provider
            model_type: Type of model
            model_name: Name of the model
            
        Returns:
            Model instance if found, None otherwise
        """
        model_id = f"{provider.value}_{model_type.value}_{model_name}"
        return self._initialized_models.get(model_id)
    
    async def create_openai_model(self, model_name: str, api_key: str,
                                 organization: Optional[str] = None,
                                 **kwargs) -> BaseAIModel:
        """
        Convenience method to create OpenAI model
        
        Args:
            model_name: OpenAI model name
            api_key: OpenAI API key
            organization: OpenAI organization (optional)
            **kwargs: Additional configuration
            
        Returns:
            Initialized OpenAI model
        """
        config = {
            'api_key': api_key,
            'organization': organization,
            **kwargs
        }
        
        return await self.create_model(
            ModelProvider.OPENAI,
            ModelType.OPENAI_GPT,
            model_name,
            config
        )
    
    async def create_local_model(self, model_name: str, model_path: str,
                               **kwargs) -> BaseAIModel:
        """
        Convenience method to create local LLM model
        
        Args:
            model_name: Model identifier
            model_path: Path to model files
            **kwargs: Additional configuration
            
        Returns:
            Initialized local model
        """
        config = {
            'model_path': model_path,
            **kwargs
        }
        
        return await self.create_model(
            ModelProvider.HUGGINGFACE,
            ModelType.LOCAL_LLM,
            model_name,
            config
        )
    
    async def create_embedding_model(self, model_name: str, provider: ModelProvider,
                                   **kwargs) -> BaseAIModel:
        """
        Convenience method to create embedding model
        
        Args:
            model_name: Model name
            provider: Model provider
            **kwargs: Additional configuration
            
        Returns:
            Initialized embedding model
        """
        return await self.create_model(
            provider,
            ModelType.EMBEDDING,
            model_name,
            kwargs
        )
    
    def list_models(self) -> Dict[str, Dict[str, Any]]:
        """
        List all initialized models
        
        Returns:
            Dictionary of model information
        """
        models_info = {}
        
        for model_id, model in self._initialized_models.items():
            models_info[model_id] = {
                'model_name': model.model_name,
                'model_type': model.model_type.value,
                'version': model.version,
                'is_initialized': model.is_initialized,
                'capabilities': {
                    'max_context_length': getattr(model, 'capabilities', {}).max_context_length if hasattr(model, 'capabilities') else None,
                    'supports_streaming': getattr(model, 'capabilities', {}).supports_streaming if hasattr(model, 'capabilities') else None,
                    'deterministic': getattr(model, 'capabilities', {}).deterministic if hasattr(model, 'capabilities') else None
                }
            }
        
        return models_info
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Run health check on all initialized models
        
        Returns:
            Health status for all models
        """
        health_status = {}
        
        for model_id, model in self._initialized_models.items():
            try:
                health_status[model_id] = await model.health_check()
            except Exception as e:
                health_status[model_id] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return health_status

# Global model factory instance
model_factory = ModelFactory()

# Register default models
model_factory.register_model(ModelProvider.OPENAI, ModelType.OPENAI_GPT, OpenAIModel)
# Additional models will be registered when their implementations are complete
