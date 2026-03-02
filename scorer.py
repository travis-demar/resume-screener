"""Resume scoring using Anthropic Claude API with configurable criteria."""

import os
import json
import yaml
import anthropic


def load_config():
    """Load scoring configuration from config.yaml."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class ResumeScorer:
    """Score resumes using Claude API based on configurable criteria."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.config = load_config()
        self.criteria = self.config["scoring"]["criteria"]
        self.weight_values = self.config["scoring"]["weight_values"]

    def _build_prompt(self, resume_text: str, job_title: str, candidate_name: str) -> str:
        """Build the scoring prompt from config criteria."""
        criteria_text = ""
        for i, criterion in enumerate(self.criteria, 1):
            weight_label = criterion["weight"].replace("_", " ").title()
            criteria_text += f"""{i}. **{criterion["label"]}** (Weight: {weight_label})
{criterion["description"]}
"""

        criteria_names = [c["name"] for c in self.criteria]
        json_fields = ",\n    ".join([f'"{name}": <score 1-10>' for name in criteria_names])

        prompt = f"""You are an expert recruiter evaluating a candidate for a Talent Lead - India role.
Score this candidate on the following criteria, each on a scale of 1-10:

{criteria_text}
Candidate Name: {candidate_name}
Job Title: {job_title}

RESUME:
{resume_text}

Respond with ONLY a JSON object in this exact format:
{{
    {json_fields},
    "fit_summary": "<one sentence on why they are or aren't a fit for this role>"
}}

SCORING GUIDANCE:
- Be rigorous and calibrated. A score of 7+ should indicate strong qualification.
- Most candidates should score between 4-7. Reserve 8-10 for exceptional matches.
- For "high" weight criteria, be especially thorough in evaluation.
- For "low_bonus" criteria, give credit if present but don't penalize if absent."""

        return prompt

    def _calculate_weighted_score(self, scores: dict) -> float:
        """Calculate weighted overall score."""
        total_weight = 0
        weighted_sum = 0

        for criterion in self.criteria:
            name = criterion["name"]
            weight = self.weight_values.get(criterion["weight"], 1)

            if name in scores and isinstance(scores[name], (int, float)):
                weighted_sum += scores[name] * weight
                total_weight += weight

        if total_weight == 0:
            return 0

        return round(weighted_sum / total_weight, 1)

    def score_resume(self, resume_text: str, job_title: str, candidate_name: str) -> dict:
        """
        Score a resume based on configured criteria.

        Returns:
            dict with individual scores, total_score, and fit_summary
        """
        if not resume_text or not resume_text.strip():
            empty_scores = {c["name"]: 0 for c in self.criteria}
            empty_scores.update({
                "total_score": 0,
                "fit_summary": "No resume text available for scoring.",
                "error": "Empty resume",
            })
            return empty_scores

        prompt = self._build_prompt(resume_text, job_title, candidate_name)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            # Parse JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            scores = json.loads(response_text)

            # Calculate weighted total score
            scores["total_score"] = self._calculate_weighted_score(scores)

            # Add criteria labels for display
            scores["criteria_labels"] = {c["name"]: c["label"] for c in self.criteria}

            return scores

        except json.JSONDecodeError as e:
            print(f"Error parsing Claude response: {e}")
            error_scores = {c["name"]: 0 for c in self.criteria}
            error_scores.update({
                "total_score": 0,
                "fit_summary": "Error parsing AI response.",
                "error": str(e),
            })
            return error_scores

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            error_scores = {c["name"]: 0 for c in self.criteria}
            error_scores.update({
                "total_score": 0,
                "fit_summary": "Error calling AI service.",
                "error": str(e),
            })
            return error_scores

    def get_score_threshold(self) -> float:
        """Get the configured score threshold for alerts."""
        return self.config["scoring"].get("threshold", 7.0)
