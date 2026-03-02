"""
Resume Screener - Automated candidate screening with Ashby, Claude, and Slack.

Polls Ashby for new applications, scores resumes using Claude,
and sends Slack alerts for high-scoring candidates.
"""

import os
import sys
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

from ashby_client import AshbyClient
from scorer import ResumeScorer
from slack_notifier import SlackNotifier
from tracker import ApplicationTracker

# Load environment variables
load_dotenv()

# Configuration (can be overridden via env vars)
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "60"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "1"))
HEALTH_CHECK_PORT = int(os.getenv("PORT", "8080"))


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks."""

    def do_GET(self):
        """Respond to GET requests with OK."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        """Suppress default logging to keep logs clean."""
        pass


def start_health_server():
    """Start the health check server in a background thread."""
    server = HTTPServer(("0.0.0.0", HEALTH_CHECK_PORT), HealthCheckHandler)
    print(f"Health check server running on port {HEALTH_CHECK_PORT}", flush=True)
    server.serve_forever()


def process_applications():
    """Fetch and process new job applications."""
    print(f"\n{'='*50}", flush=True)
    print(f"Starting application processing run...", flush=True)
    print(f"Time: {datetime.utcnow().isoformat()}Z", flush=True)
    print(f"{'='*50}", flush=True)

    try:
        # Initialize clients
        ashby = AshbyClient()
        scorer = ResumeScorer()
        slack = SlackNotifier()
        tracker = ApplicationTracker()

        # Get threshold from config
        score_threshold = scorer.get_score_threshold()

        # Fetch recent applications
        print(f"Fetching applications from the last {LOOKBACK_HOURS} hour(s)...", flush=True)
        applications = ashby.get_recent_applications(hours=LOOKBACK_HOURS)
        print(f"Found {len(applications)} application(s)", flush=True)

        new_count = 0
        alert_count = 0

        for app in applications:
            app_id = app.get("id")

            # Skip if already processed
            if tracker.is_processed(app_id):
                print(f"  Skipping {app_id} (already processed)", flush=True)
                continue

            new_count += 1

            # Get full application details
            print(f"\nProcessing application {app_id}...", flush=True)
            details = ashby.get_application_details(app)

            candidate_name = details["candidate_name"]
            candidate_id = details["candidate_id"]
            job_title = details["job_title"]
            email = details["candidate_email"]
            resume_text = details["resume_text"]

            print(f"  Candidate: {candidate_name}", flush=True)
            print(f"  Job: {job_title}", flush=True)

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

            # Decide action based on score
            if total_score >= score_threshold:
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
                    alert_count += 1
                    print(f"  Slack alert sent successfully!", flush=True)
                else:
                    print(f"  Failed to send Slack alert", flush=True)
            else:
                print(f"  Score below threshold ({score_threshold}), logging only", flush=True)
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
        print(f"\n{'='*50}", flush=True)
        print(f"Run complete!", flush=True)
        print(f"  New applications processed: {new_count}", flush=True)
        print(f"  Alerts sent this run: {alert_count}", flush=True)
        print(f"  Total processed all-time: {stats['total_processed']}", flush=True)
        print(f"{'='*50}\n", flush=True)

        return True

    except Exception as e:
        print(f"Error during processing: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return False


def main():
    """Main entry point - runs health server and polling loop."""
    # Disable output buffering
    sys.stdout.reconfigure(line_buffering=True)

    # Start health check server in background thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Initialize scorer to get config
    scorer = ResumeScorer()
    score_threshold = scorer.get_score_threshold()

    print("=" * 60, flush=True)
    print("  Resume Screener - Starting Up", flush=True)
    print("=" * 60, flush=True)
    print(f"Configuration:", flush=True)
    print(f"  Poll interval: {POLL_INTERVAL_MINUTES} minutes", flush=True)
    print(f"  Score threshold: {score_threshold}", flush=True)
    print(f"  Lookback period: {LOOKBACK_HOURS} hour(s)", flush=True)
    print(f"  Health check port: {HEALTH_CHECK_PORT}", flush=True)
    print("=" * 60, flush=True)

    # Calculate sleep time in seconds
    sleep_seconds = POLL_INTERVAL_MINUTES * 60

    # Run forever
    while True:
        # Process applications
        process_applications()

        # Wait for next run
        next_run = datetime.utcnow().isoformat()
        print(f"Sleeping for {POLL_INTERVAL_MINUTES} minutes until next run...", flush=True)
        print(f"Current time: {next_run}Z", flush=True)
        sys.stdout.flush()

        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
