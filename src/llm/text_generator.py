"""
LLM Text Generator - Generates text variations for cloned elements using OpenAI structured output.
"""
import os
from typing import List, Optional
from pydantic import BaseModel
from openai import OpenAI
from loguru import logger


class TextList(BaseModel):
    """Structured output format for LLM text generation."""
    texts: List[str]


class TextGenerator:
    """Generates text variations for UI element cloning using LLM."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize text generator.
        
        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: Model to use. Defaults to gpt-4o-mini (cheapest).
        """
        api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def generate_clone_texts(
        self, 
        element_texts: List[str], 
        num_clones: int,
        element_type: str = "element"
    ) -> List[str]:
        """Generate text variations for cloned elements.
        
        Args:
            element_texts: List of existing element texts in the group
            num_clones: Number of clone texts to generate
            element_type: Type of element (e.g., "button", "link", "list item")
        
        Returns:
            List of generated text strings
        """
        if not element_texts:
            return [f"Option {i+1}" for i in range(num_clones)]
        
        try:
            prompt = self._build_prompt(element_texts, num_clones, element_type)
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format=TextList,
                temperature=0.7,
                max_tokens=200,
            )
            
            result = response.choices[0].message.parsed
            texts = result.texts if result else []
            
            # Ensure we have enough texts
            while len(texts) < num_clones:
                texts.extend([f"Option {len(texts) + 1}"] * (num_clones - len(texts)))
            
            return texts[:num_clones]
            
        except Exception as e:
            logger.warning(f"LLM text generation failed: {e}. Using fallback variations.")
            return self._generate_fallback_variations(element_texts, num_clones)
    
    def _build_prompt(self, element_texts: List[str], num_clones: int, element_type: str) -> str:
        """Build prompt for LLM."""
        examples = ", ".join(element_texts[:5])  # Use first 5 as examples
        return f"""Generate {num_clones} short text variations for {element_type} elements.

Existing examples: {examples}

Requirements:
- Similar style and length to examples
- Distinct from each other
- Appropriate for {element_type}s
- Keep under 30 characters each"""
    
    def _generate_fallback_variations(self, element_texts: List[str], num_clones: int) -> List[str]:
        """Generate fallback variations without LLM."""
        if not element_texts:
            return [f"Option {i+1}" for i in range(num_clones)]
        
        base = element_texts[0] if element_texts else "Option"
        variations = [
            f"{base} Plus",
            f"New {base}",
            f"{base} Pro",
            f"Extra {base}",
            f"{base} 2",
            f"{base} Premium",
        ]
        
        # Cycle through variations
        result = []
        for i in range(num_clones):
            result.append(variations[i % len(variations)])
        
        return result

