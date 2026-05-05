"""Local project repository for saving and loading app work."""

from __future__ import annotations

import json
import re
import shutil
import copy
from datetime import datetime
from pathlib import Path

from app_defaults import PROJECT_SCHEMA_VERSION, PROJECT_STATE_DEFAULTS

PROJECTS_DIR = Path("projects")


def save_project(project_name: str, state: dict) -> Path:
    """Save one project JSON file and return its path."""
    if not project_name.strip():
        raise ValueError("Enter a project name before saving.")

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_name(project_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PROJECTS_DIR / f"{timestamp}_{safe_name}.json"
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_name": project_name.strip(),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "state": state,
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ValueError("Project file could not be written.") from exc
    return path


def list_projects() -> list[dict[str, str]]:
    """List saved projects newest first."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECTS_DIR.exists():
        return []

    projects = []
    for path in sorted(PROJECTS_DIR.glob("*.json"), reverse=True):
        if ".backup-" in path.stem:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            projects.append(
                {
                    "path": str(path),
                    "project_name": payload.get("project_name", path.stem),
                    "saved_at": payload.get("saved_at", ""),
                    "label": f"{payload.get('saved_at', '')} | {payload.get('project_name', path.stem)}",
                }
            )
        except Exception:
            continue
    return projects


def load_project(path: str) -> dict:
    """Load a saved project payload."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Saved project JSON is corrupted or incomplete.") from exc
    except OSError as exc:
        raise ValueError("Saved project file could not be read.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Saved project file has an invalid format.")
    state = payload.get("state")
    if not isinstance(state, dict):
        raise ValueError("Saved project file does not contain a valid state.")
    return _normalize_loaded_state(state)


def update_project(path: str, project_name: str, state: dict) -> Path:
    """Overwrite one selected project with the current app state."""
    if not project_name.strip():
        raise ValueError("Enter a project name before updating the saved project.")

    target = _validated_project_path(path)
    _backup_project_file(target)
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_name": project_name.strip(),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "state": state,
    }
    try:
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ValueError("Saved project file could not be updated.") from exc
    return target


def delete_project(path: str) -> Path:
    """Delete one saved project file and return its path."""
    resolved_target = _validated_project_path(path)
    resolved_target.unlink()
    return Path(path)


def _validated_project_path(path: str) -> Path:
    """Return a safe project path inside the local projects folder."""
    target = Path(path)
    projects_root = PROJECTS_DIR.resolve()
    resolved_target = target.resolve()

    if projects_root not in resolved_target.parents:
        raise ValueError("Selected project is outside the project repository.")
    if resolved_target.suffix.lower() != ".json":
        raise ValueError("Selected project is not a saved project file.")
    if not resolved_target.exists():
        raise ValueError("Selected project no longer exists.")

    return resolved_target


def _normalize_loaded_state(state: dict) -> dict:
    """Fill missing optional keys so older projects can still be opened."""
    normalized = copy.deepcopy(PROJECT_STATE_DEFAULTS)
    normalized.update(state)
    normalized.setdefault("source_file_bytes_b64", "")
    normalized.setdefault("sdlxliff_template_bytes_b64", "")
    normalized.setdefault("realigned_template_bytes_b64", "")
    return normalized


def _backup_project_file(path: Path) -> Path:
    """Create a simple backup before overwriting a saved project."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.stem}.backup-{timestamp}{path.suffix}")
    try:
        shutil.copy2(path, backup_path)
    except OSError as exc:
        raise ValueError("Could not create a backup before updating the project.") from exc
    return backup_path


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned.strip("_") or "project"
