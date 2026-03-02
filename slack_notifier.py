"""Slack notification module for sending candidate alerts."""

import os
import yaml
import requests


def load_config():
    """Load configuration from config.yaml."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class SlackNotifier:
    """Send notifications to Slack via webhook."""

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL environment variable not set")

        self.config = load_config()

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

    def _get_ashby_profile_url(self, candidate_id: str) -> str:
        """Generate Ashby profile URL for a candidate."""
        template = self.config.get("ashby", {}).get(
            "profile_url_template",
            "https://app.ashbyhq.com/candidates/{candidate_id}"
        )
        return template.format(candidate_id=candidate_id)

    def send_candidate_alert(
        self,
        candidate_name: str,
        job_title: str,
        email: str,
        scores: dict,
        candidate_id: str = None,
    ) -> bool:
        """Send a formatted candidate alert to Slack with score breakdown."""
        total_score = scores.get("total_score", 0)
        fit_summary = scores.get("fit_summary", "No summary available.")
        criteria_labels = scores.get("criteria_labels", {})

        # Build score breakdown fields
        score_fields = []
        criteria_order = [
            "technical_ai_ability",
            "recruiting_experience",
            "startup_vc_background",
            "builder_mentality",
            "healthcare_venture_experience",
        ]

        for criterion_name in criteria_order:
            if criterion_name in scores:
                label = criteria_labels.get(criterion_name, criterion_name.replace("_", " ").title())
                score = scores[criterion_name]
                score_fields.append({
                    "type": "mrkdwn",
                    "text": f"*{label}:*\n{score}/10",
                })

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
                    {"type": "mrkdwn", "text": f"*Overall Score:*\n{total_score}/10"},
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Score Breakdown:*",
                },
            },
        ]

        # Add score fields (Slack allows max 10 fields per section)
        if score_fields:
            blocks.append({
                "type": "section",
                "fields": score_fields[:10],
            })

        blocks.append({"type": "divider"})

        # Fit summary
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Assessment:*\n{fit_summary}",
            },
        })

        # Add Ashby profile link if candidate_id is available
        if candidate_id:
            profile_url = self._get_ashby_profile_url(candidate_id)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Email:* {email}",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in Ashby",
                        "emoji": True,
                    },
                    "url": profile_url,
                    "action_id": "view_ashby_profile",
                },
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Email:* {email}",
                },
            })

        try:
            response = requests.post(
                self.webhook_url,
                json={"blocks": blocks},
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending Slack alert: {e}")
            return False
