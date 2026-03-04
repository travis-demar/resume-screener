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
        self.weight_values = self.config.get("weight_values", {
            "critical": 5,
            "high": 3,
            "medium": 2,
            "low": 1,
            "low_bonus": 1
        })
        self.roles = {role["job_id"]: role for role in self.config.get("roles", [])}

        # Backward compatibility: if old format, create a default role
        if "scoring" in self.config and "criteria" in self.config["scoring"]:
            self._legacy_criteria = self.config["scoring"]["criteria"]
            self._legacy_threshold = self.config["scoring"].get("threshold", 7.0)
            if "weight_values" in self.config["scoring"]:
                self.weight_values = self.config["scoring"]["weight_values"]
        else:
            self._legacy_criteria = None
            self._legacy_threshold = 7.0

    def get_role_config(self, job_id: str = None, job_title: str = None) -> dict:
        """Get role configuration by job_id or job_title."""
        # Try to find by job_id first
        if job_id and job_id in self.roles:
            return self.roles[job_id]

        # Try to find by job_title
        if job_title:
            for role in self.roles.values():
                if role.get("job_title", "").lower() == job_title.lower():
                    return role

        # Fall back to legacy config or first role
        if self._legacy_criteria:
            return {
                "criteria": self._legacy_criteria,
                "threshold": self._legacy_threshold,
                "job_title": "Unknown"
            }

        # Return first role as default
        if self.roles:
            return list(self.roles.values())[0]

        return None

    def _build_prompt(self, resume_text: str, job_title: str, candidate_name: str, role_config: dict) -> str:
        """Build the scoring prompt from config criteria."""
        criteria = role_config.get("criteria", [])
        role_title = role_config.get("job_title", job_title)

        criteria_text = ""
        for i, criterion in enumerate(criteria, 1):
            weight_label = criterion["weight"].replace("_", " ").title()
            criteria_text += f"""{i}. **{criterion["label"]}** (Weight: {weight_label})
{criterion["description"]}
"""

        criteria_names = [c["name"] for c in criteria]
        json_fields = ",\n    ".join([f'"{name}": <score 1-10>' for name in criteria_names])

        # Special handling for NYC location (hard gate, not scored)
        nyc_note = ""
        if role_config.get("nyc_hard_gate"):
            nyc_note = """
NYC LOCATION CHECK (HARD GATE - NOT A SCORED DIMENSION):
- Determine if the candidate is based in NYC or the NYC metro area.
- Look for location indicators: city, state, "based in", addresses, LinkedIn location, etc.
- Include "nyc_confirmed": true/false in your response.
- This is a hard requirement - if not in NYC, the candidate will not be alerted regardless of score.
"""

        # Special handling for years of experience
        yoe_note = ""
        if any(c["name"] == "years_experience_fit" for c in criteria):
            yoe_note = """
YEARS OF EXPERIENCE GUIDANCE:
- Calculate total years of professional experience from the resume.
- Ideal range: 3-11 years = score 7-10
- 12-14 years = score 4-6
- 15+ years = score 2 or below (too senior for this role)
- Less than 2 years = score 3-4 (too junior)
- Include "years_of_experience": <number> in your response.
"""

        prompt = f"""You are an expert recruiter evaluating a candidate for the role: {role_title}

Score this candidate on the following criteria, each on a scale of 1-10:

{criteria_text}
Candidate Name: {candidate_name}
Applied for: {job_title}
{nyc_note}{yoe_note}
RESUME/PROFILE:
{resume_text}

Respond with ONLY a JSON object in this exact format:
{{
    {json_fields},
    "fit_summary": "<one sentence on why they are or aren't a fit for this role>"
}}

SCORING GUIDANCE:
- Be rigorous and calibrated. A score of 7+ should indicate strong qualification.
- Most candidates should score between 4-7. Reserve 8-10 for exceptional matches.
- For "critical" weight criteria, these are hard requirements - failing them should cap the overall score.
- For "high" weight criteria, be especially thorough in evaluation.
- For "low" or "low_bonus" criteria, give credit if present but don't penalize if absent."""

        return prompt

    def _calculate_weighted_score(self, scores: dict, role_config: dict) -> float:
        """Calculate weighted overall score."""
        criteria = role_config.get("criteria", [])
        total_weight = 0
        weighted_sum = 0

        for criterion in criteria:
            name = criterion["name"]
            weight = self.weight_values.get(criterion["weight"], 1)

            if name in scores and isinstance(scores[name], (int, float)):
                weighted_sum += scores[name] * weight
                total_weight += weight

        if total_weight == 0:
            return 0

        calculated_score = round(weighted_sum / total_weight, 1)

        # Apply NYC cap if applicable
        if "nyc_location" in scores:
            nyc_score = scores.get("nyc_location", 10)
            if nyc_score <= 4:  # Not in NYC
                calculated_score = min(calculated_score, 4.0)

        return calculated_score

    def score_resume(self, resume_text: str, job_title: str, candidate_name: str, job_id: str = None) -> dict:
        """
        Score a resume based on configured criteria for the role.

        Returns:
            dict with individual scores, total_score, and fit_summary
        """
        role_config = self.get_role_config(job_id=job_id, job_title=job_title)

        if not role_config:
            return {
                "total_score": 0,
                "fit_summary": "No role configuration found.",
                "error": "No matching role config"
            }

        criteria = role_config.get("criteria", [])

        if not resume_text or not resume_text.strip():
            empty_scores = {c["name"]: 0 for c in criteria}
            empty_scores.update({
                "total_score": 0,
                "fit_summary": "No resume text available for scoring.",
                "error": "Empty resume",
            })
            return empty_scores

        prompt = self._build_prompt(resume_text, job_title, candidate_name, role_config)

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
            base_score = self._calculate_weighted_score(scores, role_config)

            # Apply founder boost if applicable
            founder_boost = role_config.get("founder_boost", 0)
            is_founder = scores.get("is_founder", False)
            if founder_boost and is_founder:
                boosted_score = round(base_score * (1 + founder_boost), 1)
                scores["total_score"] = min(boosted_score, 10.0)  # Cap at 10
                scores["founder_boost_applied"] = True
            else:
                scores["total_score"] = base_score
                scores["founder_boost_applied"] = False

            # Add criteria labels for display
            scores["criteria_labels"] = {c["name"]: c["label"] for c in criteria}

            return scores

        except json.JSONDecodeError as e:
            print(f"Error parsing Claude response: {e}")
            error_scores = {c["name"]: 0 for c in criteria}
            error_scores.update({
                "total_score": 0,
                "fit_summary": "Error parsing AI response.",
                "error": str(e),
            })
            return error_scores

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            error_scores = {c["name"]: 0 for c in criteria}
            error_scores.update({
                "total_score": 0,
                "fit_summary": "Error calling AI service.",
                "error": str(e),
            })
            return error_scores

    def get_score_threshold(self, job_id: str = None, job_title: str = None) -> float:
        """Get the configured score threshold for alerts."""
        role_config = self.get_role_config(job_id=job_id, job_title=job_title)
        if role_config:
            return role_config.get("threshold", 7.0)
        return self._legacy_threshold
