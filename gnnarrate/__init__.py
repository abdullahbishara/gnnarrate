"""GNNarrate -- LLM-generated narratives for CLARUS graph neural network explanations."""

from .benchmark import (
    BatchMitigationResult,
    BenchmarkResult,
    NarrativeRecord,
    generate_records,
    llm_generator,
    run_batch_mitigation,
    run_benchmark,
    score_record,
)
from .clarus_log import ParsedLog, parse_clarus_log
from .faithfulness import FaithfulnessReport, score_faithfulness
from .grounding import DiseaseAssociations, GroundingReport, score_grounding
from .llm import DEFAULT_MODELS, explain_model_prediction
from .mitigation import (
    MitigationResult,
    build_revision_prompt,
    llm_reviser,
    measure_mitigation,
    mitigate,
)
from .prompts import DEFAULT_XAI_METHODS, generate_gnn_explanation_prompt
from .server import llm_blueprint

__version__ = "0.1.0"

__all__ = [
    "generate_gnn_explanation_prompt",
    "explain_model_prediction",
    "llm_blueprint",
    "parse_clarus_log",
    "ParsedLog",
    "score_faithfulness",
    "FaithfulnessReport",
    "score_grounding",
    "GroundingReport",
    "DiseaseAssociations",
    "run_benchmark",
    "run_batch_mitigation",
    "score_record",
    "generate_records",
    "llm_generator",
    "BenchmarkResult",
    "BatchMitigationResult",
    "NarrativeRecord",
    "mitigate",
    "measure_mitigation",
    "build_revision_prompt",
    "llm_reviser",
    "MitigationResult",
    "DEFAULT_MODELS",
    "DEFAULT_XAI_METHODS",
]
