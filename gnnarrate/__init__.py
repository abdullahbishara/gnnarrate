"""GNNarrate -- LLM-generated narratives for CLARUS graph neural network explanations."""

from .llm import DEFAULT_MODELS, explain_model_prediction
from .prompts import DEFAULT_XAI_METHODS, generate_gnn_explanation_prompt
from .server import llm_blueprint

__version__ = "0.1.0"

__all__ = [
    "generate_gnn_explanation_prompt",
    "explain_model_prediction",
    "llm_blueprint",
    "DEFAULT_MODELS",
    "DEFAULT_XAI_METHODS",
]
