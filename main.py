"""
Resume Screener - Automated candidate screening with Ashby, Claude, and Slack.

Polls Ashby for new applications, scores resumes using Claude,
and sends Slack alerts for high-scoring candidates.
"""

import os
import time
import schedule
from dotenv import load_dotenv

from ashby_client import AshbyClient
from scorer import ResumeScorer
from slack_notifier import SlackNotifier
from tracker import ApplicationTracker

# Load environment variables
load_dotenv()

# Configuration
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "60"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "7.0"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "1"))


def process_applications():
    """Fetch and process new job applications."""
    print(f"\n{'='*50}")
    print(f"Starting application processing run...")
    print(f"{'='*50}")

    try:
        # Initialize clients
        ashby = AshbyClient()
        scorer = ResumeScorer()
        slack = SlackNotifier()
        tracker = ApplicationTracker()

        # Fetch recent applications
        print(f"Fetching applications from the last {LOOKBACK_HOURS} hour(s)...")
        applications = ashby.get_recent_applications(hours=LOOKBACK_HOURS)
        print(f"Found {len(applications)} application(s)")

        new_count = 0
        alert_count = 0

        for app in applications:
            app_id = app.get("id")

            # Skip if already processed
            if tracker.is_processed(app_id):
                print(f"  Skipping {app_id} (already processed)")
                continue

            new_count += 1

            # Get full application details
            print(f"\nProcessing application {app_id}...")
            details = ashby.get_application_details(app)

            candidate_name = details["candidate_name"]
            job_title = details["job_title"]
            email = details["candidate_email"]
            resume_text = details["resume_text"]

            print(f"  Candidate: {candidate_name}")
            print(f"  Job: {job_title}")

            # Score the resume
            print(f"  Scoring resume...")
            scores = scorer.score_resume(resume_text, job_title, candidate_name)
            total_score = scores.get("total_score", 0)

            print(f"  Scores: Healthcare={scores.get('healthcare_experience')}, "
                  f"Startup={scores.get('startup_venture_experience')}, "
                  f"Role Fit={scores.get('role_relevance')}")
            print(f"  Total Score: {total_score}/10")

            # Decide action based on score
            if total_score >= SCORE_THRESHOLD:
                print(f"  :star: HIGH SCORE - Sending Slack alert...")
                success = slack.send_candidate_alert(
                    candidate_name=candidate_name,
                    job_title=job_title,
                    email=email,
                    scores=scores,
                )
                recommendation = "alert"
                if success:
                    alert_count += 1
                    print(f"  Slack alert sent successfully!")
                else:
                    print(f"  Failed to send Slack alert")
            else:
                print(f"  Score below threshold ({SCORE_THRESHOLD}), logging only")
                recommendation = "skip"

            # Mark as processed
            tracker.mark_processed(
                application_id=app_id,
                candidate_name=candidate_name,
                score=total_score,
                recommendation=recommendation,
            )

        # Summary
        stats = tracker.get_stats()
        print(f"\n{'='*50}")
        print(f"Run complete!")
        print(f"  New applications processed: {new_count}")
        print(f"  Alerts sent this run: {alert_count}")
        print(f"  Total processed all-time: {stats['total_processed']}")
        print(f"{'='*50}\n")

    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point - runs the polling loop."""
    print("=" * 60)
    print("  Resume Screener - Starting Up")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Poll interval: {POLL_INTERVAL_MINUTES} minutes")
    print(f"  Score threshold: {SCORE_THRESHOLD}")
    print(f"  Lookback period: {LOOKBACK_HOURS} hour(s)")
    print("=" * 60)

    # Run immediately on startup
    process_applications()

    # Schedule regular polling
    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(process_applications)

    print(f"Scheduler started. Polling every {POLL_INTERVAL_MINUTES} minutes...")
    print("Press Ctrl+C to stop.\n")

    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    main()
