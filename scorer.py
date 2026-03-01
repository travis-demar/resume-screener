"""Resume scoring using Anthropic Claude API."""

import os
import json
import anthropic


class ResumeScorer:
    """Score resumes using Claude API."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=api_key)

    def score_resume(self, resume_text: str, job_title: str, candidate_name: str) -> dict:
        """
        Score a resume on healthcare experience, startup/venture experience,
        and role relevance.

        Returns:
            dict with scores, total_score, and summary
        """
        if not resume_text or not resume_text.strip():
            return {
                "healthcare_experience": 0,
                "startup_venture_experience": 0,
                "role_relevance": 0,
                "total_score": 0,
                "summary": "No resume text available for scoring.",
                "error": "Empty resume",
            }

        prompt = f"""You are an expert recruiter evaluating a candidate's resume.
Score this candidate on the following criteria, each on a scale of 1-10:

1. **Healthcare Experience**: Experience in healthcare, healthtech, biotech, medical devices,
   health insurance, hospital systems, or related fields. Consider depth, relevance, and recency.

2. **Startup/Venture Experience**: Experience at startups, venture-backed companies,
   venture capital firms, or high-growth environments. Early-stage experience counts more.

3. **Role Relevance**: How well the candidate's background matches the role "{job_title}".
   Consider skills, seniority level, and career trajectory.

Candidate Name: {candidate_name}
Job Title: {job_title}

RESUME:
{resume_text}

Respond with ONLY a JSON object in this exact format:
{{
    "healthcare_experience": <score 1-10>,
    "startup_venture_experience": <score 1-10>,
    "role_relevance": <score 1-10>,
    "summary": "<exactly 3 sentences summarizing the candidate's fit>"
}}

Be rigorous and calibrated. A score of 7+ should indicate strong qualification.
Most candidates should score between 4-7. Reserve 8-10 for exceptional matches."""

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

            # Calculate total score (average of three criteria, rounded)
            total = (
                scores["healthcare_experience"] +
                scores["startup_venture_experience"] +
                scores["role_relevance"]
            ) / 3
            scores["total_score"] = round(total, 1)

            return scores

        except json.JSONDecodeError as e:
            print(f"Error parsing Claude response: {e}")
            return {
                "healthcare_experience": 0,
                "startup_venture_experience": 0,
                "role_relevance": 0,
                "total_score": 0,
                "summary": "Error parsing AI response.",
                "error": str(e),
            }
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return {
                "healthcare_experience": 0,
                "startup_venture_experience": 0,
                "role_relevance": 0,
                "total_score": 0,
                "summary": "Error calling AI service.",
                "error": str(e),
            }
