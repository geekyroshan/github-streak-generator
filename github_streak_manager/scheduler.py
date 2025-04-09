"""
Scheduler for automatic GitHub streak maintenance.
"""

import os
import sys
import time
import random
import logging
import datetime
import argparse
import schedule
from pathlib import Path
from typing import Optional

from github_streak_manager.main import StreakManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser('~/.github_streak_manager.log'))
    ]
)
logger = logging.getLogger('streak_scheduler')

class StreakScheduler:
    """Scheduler for automating GitHub streak maintenance."""
    
    def __init__(self, repo_path: str, config_path: Optional[str] = None):
        """Initialize the streak scheduler.
        
        Args:
            repo_path: Path to the Git repository to use for streak maintenance
            config_path: Optional path to config file
        """
        self.repo_path = os.path.abspath(repo_path)
        self.manager = StreakManager(config_path)
        
        # Verify repository exists
        if not os.path.exists(os.path.join(self.repo_path, '.git')):
            logger.error(f"Not a valid Git repository: {self.repo_path}")
            sys.exit(1)
    
    def check_and_fill_streak(self) -> bool:
        """Check for missing contributions and fill if needed.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Checking GitHub contribution streak...")
        
        try:
            # Analyze current streak
            streak_info = self.manager.analyze_streak()
            
            # Get today's date
            today = datetime.date.today().isoformat()
            
            # Check if we've already contributed today
            if today not in streak_info["missing_dates"]:
                logger.info("Already have a contribution for today! No action needed.")
                return True
            
            # We need to make a contribution for today
            logger.info("No contribution found for today. Creating one...")
            
            # Create a commit for today with a random commit message
            success = self.manager.backdate_commit(
                repo_path=self.repo_path,
                date=today,
                push=True
            )
            
            if success:
                logger.info("Successfully created commit for today!")
                return True
            else:
                logger.error("Failed to create commit for today.")
                return False
            
        except Exception as e:
            logger.error(f"Error checking and filling streak: {e}")
            return False
    
    def schedule_daily_check(self, hour: int = None, minute: int = None) -> None:
        """Schedule a daily check to maintain GitHub streak.
        
        Args:
            hour: Hour to run the check (24-hour format, random if None)
            minute: Minute to run the check (random if None)
        """
        # If no specific time provided, pick a random time during work hours
        if hour is None:
            hour = random.randint(9, 17)  # 9 AM to 5 PM
        
        if minute is None:
            minute = random.randint(0, 59)
        
        time_str = f"{hour:02d}:{minute:02d}"
        logger.info(f"Scheduling daily streak check at {time_str}")
        
        # Schedule the job
        schedule.every().day.at(time_str).do(self.check_and_fill_streak)
    
    def run(self) -> None:
        """Run the scheduler loop."""
        logger.info(f"Starting GitHub streak scheduler for repository: {self.repo_path}")
        
        # Run once immediately to ensure we have a contribution for today
        self.check_and_fill_streak()
        
        # Run the scheduling loop
        logger.info("Entering scheduling loop. Press Ctrl+C to exit.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")


def main():
    """Command-line interface for the streak scheduler."""
    parser = argparse.ArgumentParser(description="GitHub Streak Scheduler")
    
    parser.add_argument('--repo', type=str, required=True, 
                        help='Path to the Git repository to use for streak maintenance')
    parser.add_argument('--hour', type=int, choices=range(0, 24),
                        help='Hour to run daily check (24-hour format, random if not specified)')
    parser.add_argument('--minute', type=int, choices=range(0, 60),
                        help='Minute to run daily check (random if not specified)')
    parser.add_argument('--daemon', action='store_true',
                        help='Run as a daemon process in the background')
    
    args = parser.parse_args()
    
    # Initialize scheduler
    scheduler = StreakScheduler(args.repo)
    
    # Schedule daily check
    scheduler.schedule_daily_check(args.hour, args.minute)
    
    # Run in daemon mode if requested
    if args.daemon and os.name != 'nt':  # Not supported on Windows
        try:
            import daemon
            with daemon.DaemonContext():
                scheduler.run()
        except ImportError:
            logger.warning("Python-daemon package not available. Running in foreground.")
            scheduler.run()
    else:
        # Run in foreground
        scheduler.run()


if __name__ == "__main__":
    main() 