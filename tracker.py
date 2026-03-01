"""Track processed applications to avoid duplicate scoring."""

import os
import json
from datetime import datetime


class ApplicationTracker:
    """
    Track which applications have been processed.
    Uses a simple JSON file for persistence.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.getenv(
            "TRACKER_FILE", "processed_applications.json"
        )
        self._processed = self._load()

    def _load(self) -> dict:
        """Load processed applications from storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading tracker file: {e}")
                return {}
        return {}

    def _save(self) -> None:
        """Save processed applications to storage."""
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self._processed, f, indent=2)
        except IOError as e:
            print(f"Error saving tracker file: {e}")

    def is_processed(self, application_id: str) -> bool:
        """Check if an application has already been processed."""
        return application_id in self._processed

    def mark_processed(
        self,
        application_id: str,
        candidate_name: str,
        score: float,
        recommendation: str,
    ) -> None:
        """Mark an application as processed."""
        self._processed[application_id] = {
            "candidate_name": candidate_name,
            "score": score,
            "recommendation": recommendation,
            "processed_at": datetime.utcnow().isoformat() + "Z",
        }
        self._save()

    def get_stats(self) -> dict:
        """Get statistics about processed applications."""
        total = len(self._processed)
        alerted = sum(
            1 for app in self._processed.values()
            if app.get("recommendation") == "alert"
        )
        skipped = total - alerted

        return {
            "total_processed": total,
            "alerted": alerted,
            "skipped": skipped,
        }

    def clear(self) -> None:
        """Clear all processed applications (use with caution)."""
        self._processed = {}
        self._save()
