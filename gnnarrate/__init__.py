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
from .annotation import compute_agreement, export_claims_for_annotation, extract_claims
from .judge import (
    DirectionResult,
    aggregate_direction,
    llm_direction_judge,
    score_direction,
)
from .mitigation import (
    MitigationResult,
    build_revision_prompt,
    claim_level_reviser,
    llm_reviser,
    measure_mitigation,
    mitigate,
    symbolic_reviser,
)
from .stats import format_ci, mean_ci
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
    "symbolic_reviser",
    "claim_level_reviser",
    "MitigationResult",
    "mean_ci",
    "format_ci",
    "extract_claims",
    "export_claims_for_annotation",
    "compute_agreement",
    "score_direction",
    "aggregate_direction",
    "llm_direction_judge",
    "DirectionResult",
    "DEFAULT_MODELS",
    "DEFAULT_XAI_METHODS",
]
