"""Ashby API client for fetching job applications and candidate data."""

import os
import requests
from base64 import b64encode
from datetime import datetime, timedelta


class AshbyClient:
    """Client for interacting with the Ashby API."""

    BASE_URL = "https://api.ashbyhq.com"

    def __init__(self):
        api_key = os.getenv("ASHBY_API_KEY")
        if not api_key:
            raise ValueError("ASHBY_API_KEY environment variable not set")

        # Ashby uses Basic Auth with API key as username, empty password
        credentials = b64encode(f"{api_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    def _request(self, endpoint: str, data: dict = None) -> dict:
        """Make a POST request to the Ashby API."""
        response = requests.post(
            f"{self.BASE_URL}{endpoint}",
            headers=self.headers,
            json=data or {},
        )
        response.raise_for_status()
        return response.json()

    def list_open_jobs(self) -> list:
        """List all open jobs."""
        result = self._request("/job.list", {"status": "Open"})
        return result.get("results", [])

    def get_recent_applications(self, hours: int = 1) -> list:
        """Fetch applications submitted in the last N hours."""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = self._request("/application.list", {
            "createdAfter": since.isoformat() + "Z",
        })
        return result.get("results", [])

    def get_candidate(self, candidate_id: str) -> dict:
        """Fetch candidate details by ID."""
        result = self._request("/candidate.info", {"id": candidate_id})
        return result.get("results", {})

    def get_job(self, job_id: str) -> dict:
        """Fetch job details by ID."""
        result = self._request("/job.info", {"id": job_id})
        return result.get("results", {})

    def get_candidate_resume_text(self, candidate_id: str) -> str:
        """Fetch the parsed resume text for a candidate."""
        try:
            result = self._request("/candidate.listDocuments", {
                "candidateId": candidate_id,
            })
            documents = result.get("results", [])

            for doc in documents:
                if doc.get("type") == "Resume" and doc.get("parsedContent"):
                    return doc["parsedContent"]

            # Fallback: try to get resume from candidate info
            candidate = self.get_candidate(candidate_id)
            if candidate.get("resume", {}).get("text"):
                return candidate["resume"]["text"]

            return ""
        except Exception as e:
            print(f"Error fetching resume for candidate {candidate_id}: {e}")
            return ""

    def get_application_details(self, application: dict) -> dict:
        """Get full details for an application including candidate and job info."""
        candidate_id = application.get("candidateId")
        job_id = application.get("jobId")

        candidate = self.get_candidate(candidate_id) if candidate_id else {}
        job = self.get_job(job_id) if job_id else {}
        resume_text = self.get_candidate_resume_text(candidate_id) if candidate_id else ""

        # Extract candidate name
        name = candidate.get("name") or ""
        if not name:
            first = candidate.get("firstName", "")
            last = candidate.get("lastName", "")
            name = f"{first} {last}".strip()

        # Extract email
        email = ""
        if candidate.get("primaryEmailAddress", {}).get("value"):
            email = candidate["primaryEmailAddress"]["value"]
        elif candidate.get("emailAddresses"):
            email = candidate["emailAddresses"][0].get("value", "")

        return {
            "application_id": application.get("id"),
            "candidate_id": candidate_id,
            "candidate_name": name or "Unknown",
            "candidate_email": email,
            "job_id": job_id,
            "job_title": job.get("title", "Unknown Position"),
            "resume_text": resume_text,
            "applied_at": application.get("createdAt"),
        }
