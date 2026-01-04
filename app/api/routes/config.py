"""Configuration management API routes."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Config file paths
CLEANUP_CONFIG_PATH = Path("data/cleanup_config.json")
WHISPER_CONFIG_PATH = Path("data/whisper_config.json")


class ConfigResponse(BaseModel):
    """Response model for config endpoints."""

    success: bool
    config: dict[str, Any]


class ConfigUpdateRequest(BaseModel):
    """Request model for updating config."""

    config: dict[str, Any]


def load_config(path: Path) -> dict:
    """Load config from JSON file."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")
    return {}


def save_config(path: Path, config: dict) -> bool:
    """Save config to JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save config to {path}: {e}")
        return False


# Cleanup config endpoints


@router.get("/cleanup", response_model=ConfigResponse)
def get_cleanup_config():
    """Get current cleanup configuration."""
    config = load_config(CLEANUP_CONFIG_PATH)
    return ConfigResponse(success=True, config=config)


@router.put("/cleanup", response_model=ConfigResponse)
def update_cleanup_config(request: ConfigUpdateRequest):
    """Update cleanup configuration."""
    if save_config(CLEANUP_CONFIG_PATH, request.config):
        return ConfigResponse(success=True, config=request.config)
    raise HTTPException(status_code=500, detail="Failed to save cleanup config")


@router.post("/cleanup/term-correction")
def add_term_correction(wrong: str, correct: str):
    """Add a single term correction to cleanup config."""
    config = load_config(CLEANUP_CONFIG_PATH)
    if "term_corrections" not in config:
        config["term_corrections"] = {}
    config["term_corrections"][wrong] = correct
    if save_config(CLEANUP_CONFIG_PATH, config):
        return {"success": True, "term_corrections": config["term_corrections"]}
    raise HTTPException(status_code=500, detail="Failed to save config")


@router.delete("/cleanup/term-correction/{wrong}")
def remove_term_correction(wrong: str):
    """Remove a term correction from cleanup config."""
    config = load_config(CLEANUP_CONFIG_PATH)
    if "term_corrections" in config and wrong in config["term_corrections"]:
        del config["term_corrections"][wrong]
        if save_config(CLEANUP_CONFIG_PATH, config):
            return {"success": True, "removed": wrong}
    raise HTTPException(status_code=404, detail=f"Term correction '{wrong}' not found")


@router.post("/cleanup/few-shot-example")
def add_few_shot_example(input_text: str, output_text: str):
    """Add a few-shot example to cleanup config."""
    config = load_config(CLEANUP_CONFIG_PATH)
    if "few_shot_examples" not in config:
        config["few_shot_examples"] = []
    config["few_shot_examples"].append({"input": input_text, "output": output_text})
    if save_config(CLEANUP_CONFIG_PATH, config):
        return {"success": True, "example_count": len(config["few_shot_examples"])}
    raise HTTPException(status_code=500, detail="Failed to save config")


# Whisper config endpoints


@router.get("/whisper", response_model=ConfigResponse)
def get_whisper_config():
    """Get current Whisper configuration."""
    config = load_config(WHISPER_CONFIG_PATH)
    return ConfigResponse(success=True, config=config)


@router.put("/whisper", response_model=ConfigResponse)
def update_whisper_config(request: ConfigUpdateRequest):
    """Update Whisper configuration."""
    if save_config(WHISPER_CONFIG_PATH, request.config):
        return ConfigResponse(success=True, config=request.config)
    raise HTTPException(status_code=500, detail="Failed to save Whisper config")


@router.put("/whisper/initial-prompt/{language}")
def set_whisper_initial_prompt(language: str, prompt: str):
    """Set initial prompt for a specific language."""
    config = load_config(WHISPER_CONFIG_PATH)
    if "initial_prompts" not in config:
        config["initial_prompts"] = {}
    config["initial_prompts"][language] = prompt
    if save_config(WHISPER_CONFIG_PATH, config):
        return {"success": True, "language": language, "prompt": prompt}
    raise HTTPException(status_code=500, detail="Failed to save config")
