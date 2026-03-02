"""
Bulk Resume Screener - One-time script to screen ALL existing applications.

This script fetches all applications from Ashby (regardless of date),
scores each one, and sends Slack alerts for high-scoring candidates.

Usage:
    python bulk_screen.py
"""

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

from ashby_client import AshbyClient
from scorer import ResumeScorer
from slack_notifier import SlackNotifier
from tracker import ApplicationTracker

# Load environment variables
load_dotenv()

# Configuration
DELAY_BETWEEN_CANDIDATES = 2.5  # seconds


def fetch_all_applications(ashby: AshbyClient) -> list:
    """Fetch all applications from Ashby without date filtering."""
    print("Fetching all applications from Ashby...", flush=True)

    # Use a very large lookback to get all applications
    # Ashby API may paginate - we'll fetch as many as possible
    all_applications = []

    try:
        # Try fetching with no date filter by using a large lookback
        # 10 years = 87600 hours
        result = ashby._request("/application.list", {})
        applications = result.get("results", [])
        all_applications.extend(applications)

        # Handle pagination if present
        while result.get("nextCursor"):
            print(f"  Fetching next page (cursor: {result['nextCursor'][:20]}...)", flush=True)
            result = ashby._request("/application.list", {
                "cursor": result["nextCursor"]
            })
            applications = result.get("results", [])
            all_applications.extend(applications)

    except Exception as e:
        print(f"Error fetching applications: {e}", flush=True)

    return all_applications


def bulk_screen():
    """Screen all existing applications in Ashby."""
    print("=" * 60, flush=True)
    print("  Bulk Resume Screener - Starting", flush=True)
    print(f"  Time: {datetime.utcnow().isoformat()}Z", flush=True)
    print("=" * 60, flush=True)

    # Initialize clients
    ashby = AshbyClient()
    scorer = ResumeScorer()
    slack = SlackNotifier()
    tracker = ApplicationTracker()

    score_threshold = scorer.get_score_threshold()
    print(f"Score threshold for alerts: {score_threshold}", flush=True)
    print(f"Delay between candidates: {DELAY_BETWEEN_CANDIDATES}s", flush=True)
    print("=" * 60, flush=True)

    # Fetch all applications
    applications = fetch_all_applications(ashby)
    total_count = len(applications)
    print(f"\nFound {total_count} total applications", flush=True)

    if total_count == 0:
        print("No applications to process. Exiting.", flush=True)
        return

    # Tracking stats
    reviewed_count = 0
    skipped_count = 0
    high_score_count = 0
    alerts_sent = 0
    errors = 0

    # Process each application
    for i, app in enumerate(applications, 1):
        app_id = app.get("id")

        print(f"\n[{i}/{total_count}] Processing application {app_id}...", flush=True)

        # Check if already processed
        if tracker.is_processed(app_id):
            print(f"  Already processed, skipping.", flush=True)
            skipped_count += 1
            continue

        try:
            # Get full application details
            details = ashby.get_application_details(app)

            candidate_name = details["candidate_name"]
            candidate_id = details["candidate_id"]
            job_title = details["job_title"]
            email = details["candidate_email"]
            resume_text = details["resume_text"]

            print(f"  Candidate: {candidate_name}", flush=True)
            print(f"  Job: {job_title}", flush=True)

            if not resume_text or not resume_text.strip():
                print(f"  No resume text available, skipping.", flush=True)
                tracker.mark_processed(
                    application_id=app_id,
                    candidate_name=candidate_name,
                    score=0,
                    recommendation="skip_no_resume",
                )
                skipped_count += 1
                continue

            # Score the resume
            print(f"  Scoring resume...", flush=True)
            scores = scorer.score_resume(resume_text, job_title, candidate_name)
            total_score = scores.get("total_score", 0)

            # Log scores
            print(f"  Scores:", flush=True)
            print(f"    Technical/AI: {scores.get('technical_ai_ability', 'N/A')}/10", flush=True)
            print(f"    Recruiting: {scores.get('recruiting_experience', 'N/A')}/10", flush=True)
            print(f"    Startup/VC: {scores.get('startup_vc_background', 'N/A')}/10", flush=True)
            print(f"    Builder: {scores.get('builder_mentality', 'N/A')}/10", flush=True)
            print(f"    Healthcare: {scores.get('healthcare_venture_experience', 'N/A')}/10", flush=True)
            print(f"  Total Score: {total_score}/10", flush=True)
            print(f"  Assessment: {scores.get('fit_summary', 'N/A')}", flush=True)

            reviewed_count += 1

            # Decide action based on score
            if total_score >= score_threshold:
                high_score_count += 1
                print(f"  *** HIGH SCORE - Sending Slack alert...", flush=True)
                success = slack.send_candidate_alert(
                    candidate_name=candidate_name,
                    job_title=job_title,
                    email=email,
                    scores=scores,
                    candidate_id=candidate_id,
                )
                recommendation = "alert"
                if success:
                    alerts_sent += 1
                    print(f"  Slack alert sent!", flush=True)
                else:
                    print(f"  Failed to send Slack alert", flush=True)
            else:
                print(f"  Score below threshold, no alert.", flush=True)
                recommendation = "skip"

            # Mark as processed
            tracker.mark_processed(
                application_id=app_id,
                candidate_name=candidate_name,
                score=total_score,
                recommendation=recommendation,
            )

        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            errors += 1

        # Delay before next candidate (except for last one)
        if i < total_count:
            time.sleep(DELAY_BETWEEN_CANDIDATES)

    # Print summary
    print("\n" + "=" * 60, flush=True)
    print("  BULK SCREENING COMPLETE", flush=True)
    print("=" * 60, flush=True)
    print(f"  Total applications found:    {total_count}", flush=True)
    print(f"  Already processed (skipped): {skipped_count}", flush=True)
    print(f"  Candidates reviewed:         {reviewed_count}", flush=True)
    print(f"  Scored 7+ (high score):      {high_score_count}", flush=True)
    print(f"  Slack alerts sent:           {alerts_sent}", flush=True)
    print(f"  Errors:                      {errors}", flush=True)
    print("=" * 60, flush=True)
    print(f"  Completed at: {datetime.utcnow().isoformat()}Z", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    bulk_screen()
