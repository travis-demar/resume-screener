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

        # Build score breakdown fields dynamically from criteria_labels
        score_fields = []
        for criterion_name, label in criteria_labels.items():
            if criterion_name in scores:
                score = scores[criterion_name]
                score_fields.append({
                    "type": "mrkdwn",
                    "text": f"*{label}:*\n{score}/10",
                })

        # Build extra info based on role-specific fields
        extra_info = []

        # EA role fields
        if "nyc_confirmed" in scores:
            nyc_status = "Yes" if scores["nyc_confirmed"] else "No"
            extra_info.append(f"*NYC Location:* {nyc_status}")
        if "years_of_experience" in scores:
            extra_info.append(f"*Years of Experience:* {scores['years_of_experience']}")

        # MD New Ventures role fields
        if "venture_tier" in scores:
            extra_info.append(f"*Venture Tier:* {scores['venture_tier']}")
        if scores.get("founder_boost_applied"):
            extra_info.append("*Founder Boost:* +5% applied")
        if "career_trajectory_summary" in scores:
            extra_info.append(f"*Career:* {scores['career_trajectory_summary']}")

        # Director of Global Development, India role fields (dual-track)
        if "track_used" in scores:
            track_display = scores["track_used"]
            if track_display.startswith("A"):
                track_label = "Track A: Investor/Banker"
            else:
                track_label = "Track B: Founder/Operator"
            if "Hybrid" in track_display:
                track_label += " (Hybrid)"
            extra_info.append(f"*Scoring Track:* {track_label}")
        if "track_reasoning" in scores:
            extra_info.append(f"*Track Reasoning:* {scores['track_reasoning']}")
        if "work_experience_tier" in scores:
            extra_info.append(f"*Work Experience Tier:* {scores['work_experience_tier']}")
        if "education_tier" in scores:
            extra_info.append(f"*Education Tier:* {scores['education_tier']}")
        if "is_founder" in scores and "track_used" not in scores:
            # Only show founder status if not already shown via track
            founder_status = "Yes" if scores["is_founder"] else "No"
            extra_info.append(f"*Former Founder:* {founder_status}")
        elif "is_founder" in scores and scores.get("track_used", "").startswith("B"):
            # Show founder status for Track B
            founder_status = "Yes" if scores["is_founder"] else "No"
            extra_info.append(f"*Former Founder:* {founder_status}")
        if "career_summary" in scores:
            extra_info.append(f"*Career:* {scores['career_summary']}")
        if scores.get("insufficient_data"):
            extra_info.append(f"*Note:* {scores.get('data_note', 'Limited profile data')}")

        # MD Ventures India role fields
        if "location_signal" in scores:
            extra_info.append(f"*Location Signal:* {scores['location_signal']}")

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
        ]

        # Add extra info if present (NYC confirmed, years of experience)
        if extra_info:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": " | ".join(extra_info),
                },
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Score Breakdown:*",
            },
        })

        # Add score fields (Slack allows max 10 fields per section)
        if score_fields:
            # Split into chunks of 10 if needed
            for i in range(0, len(score_fields), 10):
                blocks.append({
                    "type": "section",
                    "fields": score_fields[i:i+10],
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
