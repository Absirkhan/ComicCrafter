"""API client implementations for various AI services."""

import os
from typing import Optional, Dict, Any
import requests
from abc import ABC, abstractmethod
from openai import OpenAI
from utils import get_config, get_logger

logger = get_logger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM API clients."""
    
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text from a prompt.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional model-specific parameters
            
        Returns:
            Generated text
        """
        pass


class GroqClient(LLMClient):
    """Client for Groq API (Llama 3.3)."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize Groq client.
        
        Args:
            api_key: Groq API key. If None, uses config
            model: Model name. If None, uses config default
        """
        config = get_config()
        self.api_key = api_key or config.groq_api_key
        self.model = model or config.default_llm_model
        
        if not self.api_key:
            raise ValueError("Groq API key not provided")
        
        # Imported here so the comic pipeline (which loads this module) does not need the groq package.
        from groq import Groq

        self.client = Groq(api_key=self.api_key)
        logger.info(f"Initialized GroqClient with model: {self.model}")
    
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text using Groq API.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            result = response.choices[0].message.content
            logger.debug(f"Generated text: {result[:100]}...")
            return result
        except Exception as e:
            logger.error(f"Error generating text with Groq: {e}")
            raise


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterTextClient(LLMClient):
    """Client for text models on OpenRouter (OpenAI-compatible chat API).

    Credentials and model come only from OpenRouter settings (OPENROUTER_API_KEY,
    OPENROUTER_MODEL), never from the Groq key or the Groq model default.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", "")

        if not self.api_key:
            raise ValueError("OpenRouter API key not provided (set OPENROUTER_API_KEY)")
        if not self.model:
            raise ValueError("OpenRouter model not provided (set OPENROUTER_MODEL)")

        self.client = OpenAI(api_key=self.api_key, base_url=OPENROUTER_BASE_URL)
        logger.info(f"Initialized OpenRouterTextClient with model: {self.model}")

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text with the configured OpenRouter model."""
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating text with OpenRouter ({self.model}): {e}")
            raise


class GeminiClient(LLMClient):
    """Client for Google Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key. If None, uses config
            model: Model name. If None, uses config default
        """
        config = get_config()
        self.api_key = api_key or config.google_api_key
        self.model = model or config.gemini_model
        
        if not self.api_key:
            raise ValueError("Google API key not provided")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        logger.info(f"Initialized GeminiClient with model: {self.model}")
    
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text using Gemini API.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        try:
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                }
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            logger.debug(f"Generated text: {result[:100]}...")
            return result
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {e}")
            raise


LLM_PROVIDERS = {
    "groq": GroqClient,
    "gemini": GeminiClient,
    "openrouter": OpenRouterTextClient,
}


def make_llm_client(provider: str) -> LLMClient:
    """Build the text client for a provider name ("groq", "gemini" or "openrouter")."""
    try:
        client_class = LLM_PROVIDERS[provider.lower()]
    except KeyError:
        raise ValueError(f"Unknown LLM provider: {provider}") from None
    return client_class()


class HuggingFaceClient:
    """Client for HuggingFace Inference API."""
    
    def __init__(self, token: Optional[str] = None, model: Optional[str] = None):
        """Initialize HuggingFace client.
        
        Args:
            token: HuggingFace token. If None, uses config
            model: Model name. If None, uses config default
        """
        config = get_config()
        self.token = token or config.huggingface_token
        self.model = model or config.default_image_model
        
        if not self.token:
            logger.warning("HUGGINGFACE_TOKEN is not set; image requests will fail and panels will be gray placeholders")
        
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model}"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        logger.info(f"Initialized HuggingFaceClient with model: {self.model}")
    
    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        **kwargs
    ) -> bytes:
        """Generate image using HuggingFace Inference API.
        
        Args:
            prompt: Image generation prompt
            negative_prompt: Negative prompt for guidance
            num_inference_steps: Number of denoising steps
            guidance_scale: Guidance scale for generation
            **kwargs: Additional parameters
            
        Returns:
            Image data as bytes
        """
        try:
            payload = {
                "inputs": prompt,
                "parameters": {
                    "num_inference_steps": num_inference_steps,
                    "guidance_scale": guidance_scale,
                }
            }
            
            if negative_prompt:
                payload["parameters"]["negative_prompt"] = negative_prompt
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            logger.debug(f"Generated image for prompt: {prompt[:50]}...")
            return response.content
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            logger.warning(f"HuggingFace image request failed (HTTP {status}); panel will be a gray placeholder: {e}")
            raise
    
    def generate_text(
        self,
        prompt: str,
        max_length: int = 512,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text using HuggingFace text generation models.
        
        Args:
            prompt: Input prompt
            max_length: Maximum length to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        try:
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_length": max_length,
                    "temperature": temperature,
                    **kwargs
                }
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()[0]["generated_text"]
            logger.debug(f"Generated text: {result[:100]}...")
            return result
        except Exception as e:
            logger.error(f"Error generating text with HuggingFace: {e}")
            raise
