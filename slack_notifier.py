"""Slack notification module for sending candidate alerts."""

import os
import requests


class SlackNotifier:
    """Send notifications to Slack via webhook."""

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL environment variable not set")

    def send_message(self, text: str) -> bool:
        """Send a simple text message to Slack."""
        try:
            response = requests.post(
                self.webhook_url,
                json={"text": text},
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending Slack message: {e}")
            return False

    def send_candidate_alert(
        self,
        candidate_name: str,
        job_title: str,
        email: str,
        scores: dict,
    ) -> bool:
        """Send a formatted candidate alert to Slack."""
        total_score = scores.get("total_score", 0)
        summary = scores.get("summary", "No summary available.")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":star2: High-Scoring Candidate: {candidate_name}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Job:*\n{job_title}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
                    {"type": "mrkdwn", "text": f"*Total Score:*\n{total_score}/10"},
                ],
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Healthcare:*\n{scores.get('healthcare_experience', 0)}/10",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Startup/VC:*\n{scores.get('startup_venture_experience', 0)}/10",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Role Fit:*\n{scores.get('role_relevance', 0)}/10",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{summary}",
                },
            },
        ]

        try:
            response = requests.post(
                self.webhook_url,
                json={"blocks": blocks},
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending Slack alert: {e}")
            return False
