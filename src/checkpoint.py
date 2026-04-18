"""
Checkpointing utilities.

Responses and scores are stored as JSONL (one JSON object per line) so that:
  - Each result is durable as soon as it is written.
  - A partial run can be resumed without re-calling any API.
  - The files remain human-readable and inspectable with jq/pandas.
"""

import json
from pathlib import Path


def load_checkpoint(filepath: str) -> dict:
    """
    Read a JSONL checkpoint file and return a dict keyed by (qna_id, model_name).
    Returns an empty dict if the file does not exist yet.
    """
    checkpoint: dict = {}
    path = Path(filepath)
    if not path.exists():
        return checkpoint
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                key = (entry["qna_id"], entry["model_name"])
                checkpoint[key] = entry
            except (json.JSONDecodeError, KeyError):
                # Skip malformed lines — safe to ignore for resume purposes
                continue
    return checkpoint


def save_checkpoint(filepath: str, entry: dict) -> None:
    """
    Append a single entry to a JSONL checkpoint file.
    Creates parent directories if they don't exist.
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
