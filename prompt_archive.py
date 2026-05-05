"""Local archive for generated translation prompts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


ARCHIVE_PATH = Path("data") / "prompt_archive.json"


def load_prompt_archive() -> list[dict[str, str]]:
    """Load saved prompts from disk."""
    if not ARCHIVE_PATH.exists():
        return []
    with ARCHIVE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        return []
    return data


def save_prompt_to_archive(
    prompt_text: str,
    source_language: str,
    target_language: str,
    domain: str,
    title: str = "",
) -> dict[str, str]:
    """Save a prompt as a reusable template."""
    if not prompt_text.strip():
        raise ValueError("There is no prompt to save.")

    entries = load_prompt_archive()
    entry = {
        "id": str(uuid4()),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title.strip() or _default_title(source_language, target_language, domain),
        "source_language": source_language,
        "target_language": target_language,
        "domain": domain,
        "prompt": prompt_text.strip(),
    }
    entries.insert(0, entry)
    _write_archive(entries)
    return entry


def update_prompt_in_archive(
    prompt_id: str,
    prompt_text: str,
    source_language: str,
    target_language: str,
    domain: str,
    title: str = "",
) -> dict[str, str]:
    """Update an existing saved prompt template."""
    if not prompt_id:
        raise ValueError("Load or select a saved prompt before updating it.")
    if not prompt_text.strip():
        raise ValueError("There is no prompt to update.")

    entries = load_prompt_archive()
    for entry in entries:
        if entry.get("id") != prompt_id:
            continue
        entry["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["title"] = title.strip() or entry.get("title") or _default_title(source_language, target_language, domain)
        entry["source_language"] = source_language
        entry["target_language"] = target_language
        entry["domain"] = domain
        entry["prompt"] = prompt_text.strip()
        _write_archive(entries)
        return entry

    raise ValueError("The selected prompt template could not be found in the archive.")


def import_prompt_archive(file_bytes: bytes) -> int:
    """Merge prompt archive entries from an uploaded JSON file."""
    imported = json.loads(file_bytes.decode("utf-8-sig"))
    if not isinstance(imported, list):
        raise ValueError("Prompt archive JSON must contain a list of prompt entries.")

    entries = load_prompt_archive()
    existing_ids = {entry.get("id") for entry in entries}
    added = 0
    for entry in imported:
        if not isinstance(entry, dict) or not entry.get("prompt"):
            continue
        if entry.get("id") in existing_ids:
            continue
        entry.setdefault("id", str(uuid4()))
        entry.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        entry.setdefault("title", "Imported prompt")
        entry.setdefault("source_language", "")
        entry.setdefault("target_language", "")
        entry.setdefault("domain", "")
        entries.append(entry)
        added += 1

    _write_archive(entries)
    return added


def export_prompt_archive() -> bytes:
    """Return the archive as downloadable JSON bytes."""
    return json.dumps(load_prompt_archive(), ensure_ascii=False, indent=2).encode("utf-8")


def _write_archive(entries: list[dict[str, str]]) -> None:
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ARCHIVE_PATH.open("w", encoding="utf-8") as file:
        json.dump(entries, file, ensure_ascii=False, indent=2)


def _default_title(source_language: str, target_language: str, domain: str) -> str:
    return f"{domain}: {source_language} to {target_language}"
