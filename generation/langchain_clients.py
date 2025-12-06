"""LangChain-integrated API clients for ComicCrafter."""

from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from io import BytesIO

from langchain_groq import ChatGroq
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from huggingface_hub import InferenceClient

from utils import get_config, get_logger

logger = get_logger(__name__)


class LangChainLLMClient:
    """LangChain-integrated LLM client wrapper."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize LangChain LLM client.
        
        Args:
            api_key: API key for the provider
            model: Model name
        """
        config = get_config()
        self.api_key = api_key or config.groq_api_key
        self.model = model or config.default_llm_model
        
        if not self.api_key:
            raise ValueError("API key not provided")
        
        # Initialize LangChain ChatGroq
        self.llm: BaseChatModel = ChatGroq(
            groq_api_key=self.api_key,
            model=self.model,
            temperature=0.7
        )
        
        self.parser = StrOutputParser()
        logger.info(f"Initialized LangChainLLMClient with model: {self.model}")
    
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text using LangChain LLM.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_message: Optional system message
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        try:
            # Build messages
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))
            
            # Create chain with updated temperature
            llm_with_config = self.llm.bind(
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            chain = llm_with_config | self.parser
            
            # Generate
            response = chain.invoke(messages)
            
            logger.debug(f"Generated {len(response)} characters")
            return response
            
        except Exception as e:
            logger.error(f"Error generating text with LangChain: {e}")
            raise
    
    def get_llm(self) -> BaseChatModel:
        """Get the underlying LangChain LLM.
        
        Returns:
            LangChain ChatModel instance
        """
        return self.llm


class HuggingFaceClient:
    """Client for HuggingFace Inference API (Image Generation).
    
    Note: Using huggingface_hub directly as LangChain's HF integration
    is primarily for text models.
    """
    
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
            raise ValueError("HuggingFace token not provided")
        
        self.client = InferenceClient(token=self.token)
        logger.info(f"Initialized HuggingFaceClient with model: {self.model}")
    
    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Generate an image using HuggingFace Inference API.
        
        Args:
            prompt: Text prompt for image generation
            negative_prompt: Negative prompt (what to avoid)
            **kwargs: Additional parameters
            
        Returns:
            Image data as bytes (PNG format)
        """
        try:
            # Generate image
            image = self.client.text_to_image(
                prompt=prompt,
                model=self.model,
                negative_prompt=negative_prompt,
                **kwargs
            )
            
            # Convert PIL Image to bytes
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
            
            logger.debug(f"Generated image: {len(image_bytes)} bytes")
            return image_bytes
            
        except StopIteration:
            logger.warning("Image generation returned StopIteration - retrying with simplified prompt")
            # Retry with simplified prompt
            simple_prompt = prompt.split(',')[0] if ',' in prompt else prompt
            image = self.client.text_to_image(
                prompt=simple_prompt,
                model=self.model
            )
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise


class ReplicateClient:
    """Client for Replicate API with SDXL + ControlNet support.
    
    Supports both text-to-image and image-to-image for character consistency.
    """
    
    def __init__(self, token: Optional[str] = None):
        """Initialize Replicate client.
        
        Args:
            token: Replicate API token. If None, uses config/env
        """
        import replicate
        import os
        
        config = get_config()
        self.token = token or os.getenv("REPLICATE_API_TOKEN")
        
        if not self.token:
            raise ValueError("Replicate API token not provided. Set REPLICATE_API_TOKEN in .env")
        
        # Set token for replicate library
        os.environ["REPLICATE_API_TOKEN"] = self.token
        self.replicate = replicate
        
        # Model for text-to-image (base generation)
        self.text_to_image_model = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
        
        # Model for image-to-image with ControlNet (character consistency)
        self.controlnet_model = "lucataco/sdxl-controlnet:4ba4d05646896b42fb41a33c6ead02f56f556f98b2ce57d3c2b9f04d0bc2e31a"
        
        logger.info("Initialized ReplicateClient with SDXL + ControlNet")
    
    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        reference_image: Optional[bytes] = None,
        controlnet_conditioning_scale: float = 0.8,
        **kwargs
    ) -> bytes:
        """Generate an image using Replicate API.
        
        If reference_image is provided, uses ControlNet for character consistency.
        Otherwise, uses standard text-to-image.
        
        Args:
            prompt: Text prompt for image generation
            negative_prompt: Negative prompt (what to avoid)
            reference_image: Reference image bytes for ControlNet (for consistency)
            controlnet_conditioning_scale: How strongly to follow reference (0.5-1.0)
            **kwargs: Additional parameters
            
        Returns:
            Image data as bytes (PNG format)
        """
        try:
            if reference_image:
                # Use ControlNet for character consistency
                logger.info("Using ControlNet with reference image for character consistency")
                output = self._generate_with_controlnet(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    reference_image=reference_image,
                    controlnet_conditioning_scale=controlnet_conditioning_scale,
                    **kwargs
                )
            else:
                # Standard text-to-image generation
                logger.info("Using standard text-to-image generation")
                output = self._generate_text_to_image(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    **kwargs
                )
            
            # Download image from URL
            import requests
            response = requests.get(output[0])
            response.raise_for_status()
            
            logger.debug(f"Generated image: {len(response.content)} bytes")
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating image with Replicate: {e}")
            raise
    
    def _generate_text_to_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        **kwargs
    ) -> list:
        """Generate image using SDXL text-to-image."""
        input_params = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
        }
        
        if negative_prompt:
            input_params["negative_prompt"] = negative_prompt
        
        input_params.update(kwargs)
        
        output = self.replicate.run(
            self.text_to_image_model,
            input=input_params
        )
        
        return output
    
    def _generate_with_controlnet(
        self,
        prompt: str,
        reference_image: bytes,
        negative_prompt: Optional[str] = None,
        controlnet_conditioning_scale: float = 0.8,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        **kwargs
    ) -> list:
        """Generate image using ControlNet with reference image."""
        import base64
        
        # Convert reference image to base64 data URI
        image_b64 = base64.b64encode(reference_image).decode()
        image_uri = f"data:image/png;base64,{image_b64}"
        
        input_params = {
            "image": image_uri,
            "prompt": prompt,
            "conditioning_scale": controlnet_conditioning_scale,
            "width": width,
            "height": height,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
        }
        
        if negative_prompt:
            input_params["negative_prompt"] = negative_prompt
        
        input_params.update(kwargs)
        
        output = self.replicate.run(
            self.controlnet_model,
            input=input_params
        )
        
        return output


# Backward compatibility aliases
GroqClient = LangChainLLMClient


class GeminiClient:
    """Placeholder for Gemini client (not implemented with LangChain yet)."""
    
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "GeminiClient not implemented. Use LangChainLLMClient (Groq) instead."
        )
