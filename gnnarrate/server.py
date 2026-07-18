"""Flask blueprint exposing the narration layer as an HTTP endpoint.

Register it on an existing CLARUS Flask app without modifying that app's routes:

    from gnnarrate import llm_blueprint
    app.register_blueprint(llm_blueprint)

This adds POST /llm_prediction, which accepts {"llm": "<clarus log>"} and returns
{"explanation": "<narrative>"}.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from .llm import explain_model_prediction
from .prompts import generate_gnn_explanation_prompt

logger = logging.getLogger(__name__)

llm_blueprint = Blueprint("gnnarrate", __name__)


@llm_blueprint.route("/llm_prediction", methods=["POST"])
def llm_prediction():
    """Narrate a CLARUS log posted as JSON."""
    payload = request.get_json(silent=True) or {}
    log_text = payload.get("llm", "")

    if not log_text.strip():
        return jsonify({"error": "Field 'llm' is required and must be non-empty"}), 400

    try:
        prompt = generate_gnn_explanation_prompt(
            log_text, max_sentences=8, verbose=True
        )
        return jsonify({"explanation": explain_model_prediction(prompt)})
    except RuntimeError as exc:
        # Missing API key -- a configuration problem, not a bad request.
        logger.error("gnnarrate configuration error: %s", exc)
        return jsonify({"error": str(exc)}), 500
    except Exception:
        logger.exception("gnnarrate failed to generate an explanation")
        return jsonify({"error": "Failed to generate explanation"}), 500
