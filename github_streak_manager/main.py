"""
GitHub Streak Manager - A tool to maintain GitHub contribution streaks.
"""

import os
import sys
import random
import argparse
import configparser
import datetime
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple

import requests
from git import Repo, GitCommandError

class StreakManager:
    """Main class for managing GitHub contribution streaks."""
    
    def __init__(self, config_path: Optional[str] = None, skip_token_check: bool = False):
        """Initialize the StreakManager.
        
        Args:
            config_path: Path to config file, if None uses default ~/.github_streak_manager.ini
            skip_token_check: If True, skip the token check (used during setup)
        """
        self.config_path = config_path or os.path.expanduser("~/.github_streak_manager.ini")
        self.config = self._load_config()
        self.github_token = self.config.get('github', 'token', fallback=None)
        
        if not self.github_token and not skip_token_check:
            print("No GitHub token found. Please set up your token first.")
            print("Run: github-streak-manager --setup")
            sys.exit(1)
    
    def _load_config(self) -> configparser.ConfigParser:
        """Load configuration from file."""
        config = configparser.ConfigParser()
        
        if os.path.exists(self.config_path):
            config.read(self.config_path)
        
        # Ensure required sections exist
        for section in ['github', 'preferences']:
            if section not in config:
                config[section] = {}
        
        return config
    
    def setup(self, token: str = None) -> None:
        """Set up the GitHub Streak Manager with necessary credentials.
        
        Args:
            token: GitHub Personal Access Token
        """
        if not token:
            token = input("Enter your GitHub Personal Access Token: ")
        
        self.github_token = token
        self.config['github']['token'] = token
        
        with open(self.config_path, 'w') as f:
            self.config.write(f)
        
        print(f"Configuration saved to {self.config_path}")
        print("Testing GitHub API connection...")
        
        try:
            user_data = self._github_api_request("user")
            print(f"Successfully authenticated as: {user_data.get('login')}")
        except Exception as e:
            print(f"Error connecting to GitHub API: {e}")
            sys.exit(1)
    
    def _github_api_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
        """Make a GitHub API request.
        
        Args:
            endpoint: API endpoint to request
            method: HTTP method (GET, POST, etc.)
            data: JSON data to send
            
        Returns:
            API response as dictionary
        """
        base_url = "https://api.github.com"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        url = f"{base_url}/{endpoint}"
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        if response.status_code != 200:
            error_message = f"GitHub API Error: {response.status_code} - {response.text}"
            raise Exception(error_message)
        
        return response.json()
    
    def _github_graphql_request(self, query: str, variables: Dict = None) -> Dict:
        """Make a GitHub GraphQL API request.
        
        Args:
            query: GraphQL query string
            variables: Variables for the GraphQL query
            
        Returns:
            API response as dictionary
        """
        url = "https://api.github.com/graphql"
        headers = {
            "Authorization": f"bearer {self.github_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "query": query,
            "variables": variables or {}
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            error_message = f"GitHub GraphQL API Error: {response.status_code} - {response.text}"
            raise Exception(error_message)
        
        result = response.json()
        
        if "errors" in result:
            error_message = f"GraphQL Query Error: {result['errors']}"
            raise Exception(error_message)
        
        return result["data"]
    
    def get_user_repos(self) -> List[Dict]:
        """Get list of user's repositories.
        
        Returns:
            List of repository information dictionaries
        """
        repos = self._github_api_request("user/repos?per_page=100")
        return repos
    
    def suggest_repos(self, language: Optional[str] = None) -> List[Dict]:
        """Suggest repositories for commit activity.
        
        Args:
            language: Filter by programming language
            
        Returns:
            List of repository information dictionaries
        """
        repos = self.get_user_repos()
        
        # Filter by language if specified
        if language:
            repos = [repo for repo in repos if repo.get('language') == language]
        
        # Sort by last updated (oldest first)
        repos.sort(key=lambda x: x.get('updated_at', ''))
        
        return repos
    
    def backdate_commit(self, 
                        repo_path: str, 
                        date: Union[str, datetime.datetime],
                        commit_message: Optional[str] = None,
                        file_content: Optional[str] = None,
                        file_path: Optional[str] = None,
                        push: bool = False) -> bool:
        """Create a backdated commit in the specified repository.
        
        Args:
            repo_path: Path to local git repository
            date: Date for the commit (YYYY-MM-DD format or datetime object)
            commit_message: Commit message to use
            file_content: Content to write to the file
            file_path: Path to the file to modify
            push: Whether to push the commit to GitHub
            
        Returns:
            True if commit was successful, False otherwise
        """
        # Convert string date to datetime if needed
        if isinstance(date, str):
            date = datetime.datetime.strptime(date, "%Y-%m-%d")
        
        # Add random hour, minute, second for more natural commit times
        if date.hour == 0 and date.minute == 0 and date.second == 0:
            hour = random.randint(9, 19)  # Business hours
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            date = date.replace(hour=hour, minute=minute, second=second)
        
        # Format date for Git
        git_date = date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Generate commit message if not provided
        if not commit_message:
            commit_message = self._generate_commit_message()
        
        try:
            repo = Repo(repo_path)
            
            # Default file modification if none specified
            if not file_path:
                file_path = "README.md"
            
            full_path = os.path.join(repo_path, file_path)
            
            # Create or modify the file
            if file_content is None:
                if os.path.exists(full_path):
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    # Append a newline with the current date
                    file_content = f"{content}\n\n<!-- Updated: {datetime.datetime.now().isoformat()} -->"
                else:
                    file_content = f"# Placeholder\n\nThis file was created by GitHub Streak Manager.\n\n<!-- Created: {datetime.datetime.now().isoformat()} -->"
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write the content to the file
            with open(full_path, 'w') as f:
                f.write(file_content)
            
            # Stage the changes
            repo.git.add(file_path)
            
            # Commit with backdated timestamp
            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = git_date
            env["GIT_COMMITTER_DATE"] = git_date
            
            repo.git.commit("-m", commit_message, env=env)
            
            # Push if requested
            if push:
                repo.git.push()
            
            return True
        
        except Exception as e:
            print(f"Error creating backdated commit: {e}")
            return False
    
    def _generate_commit_message(self) -> str:
        """Generate a realistic commit message.
        
        Returns:
            A randomly generated commit message
        """
        commit_messages = [
            "Update README.md",
            "Fix typo in documentation",
            "Add comments for clarity",
            "Clean up code formatting",
            "Refactor utility function",
            "Update dependencies",
            "Add missing documentation",
            "Fix minor bug in error handling",
            "Improve code readability",
            "Add unit test for edge case",
            "Optimize performance",
            "Improve error messages",
            "Update configuration",
            "Fix linting issues",
            "Add new feature implementation",
            "Implement requested changes",
            "Remove deprecated code",
            "Update documentation",
            "Fix edge case",
            "Merge recent changes",
            "Add new test cases",
            "Improve logging"
        ]
        
        return random.choice(commit_messages)
    
    def analyze_streak(self, username: Optional[str] = None) -> Dict:
        """Analyze current GitHub streak status using GraphQL API.
        
        Args:
            username: GitHub username (uses authenticated user if None)
            
        Returns:
            Dictionary with streak information
        """
        if not username:
            user_data = self._github_api_request("user")
            username = user_data.get('login')
        
        # Get the last year of contribution data using GraphQL
        query = """
        query($username: String!) {
          user(login: $username) {
            contributionsCollection {
              contributionCalendar {
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {"username": username}
        data = self._github_graphql_request(query, variables)
        
        # Process contribution data
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        contribution_days = []
        
        for week in weeks:
            for day in week["contributionDays"]:
                contribution_days.append({
                    "date": day["date"],
                    "count": day["contributionCount"]
                })
        
        # Sort by date (newest first)
        contribution_days.sort(key=lambda x: x["date"], reverse=True)
        
        # Calculate current streak
        current_streak = 0
        for day in contribution_days:
            if day["count"] > 0:
                current_streak += 1
            else:
                break
        
        # Calculate longest streak
        longest_streak = 0
        current_longest = 0
        for day in sorted(contribution_days, key=lambda x: x["date"]):
            if day["count"] > 0:
                current_longest += 1
            else:
                longest_streak = max(longest_streak, current_longest)
                current_longest = 0
        
        longest_streak = max(longest_streak, current_longest)
        
        # Find missing dates (days with no contributions in the last 30 days)
        today = datetime.date.today()
        last_30_days = [
            (today - datetime.timedelta(days=i)).isoformat() 
            for i in range(30)
        ]
        
        recent_contribution_dates = {
            day["date"] for day in contribution_days[:30]
        }
        
        missing_dates = [
            date for date in last_30_days 
            if date not in recent_contribution_dates
        ]
        
        # Get last commit date
        last_commit_date = contribution_days[0]["date"] if contribution_days and contribution_days[0]["count"] > 0 else None
        
        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "missing_dates": missing_dates,
            "last_commit_date": last_commit_date,
            "contribution_days": contribution_days[:90]  # Last 90 days
        }
    
    def bulk_backdate(self, 
                      repo_path: str,
                      dates: List[str],
                      commit_count: int = 1,
                      push: bool = False) -> Dict[str, bool]:
        """Create multiple backdated commits.
        
        Args:
            repo_path: Path to local git repository
            dates: List of dates in YYYY-MM-DD format
            commit_count: Number of commits per date
            push: Whether to push the commits to GitHub
            
        Returns:
            Dictionary mapping dates to success status
        """
        results = {}
        
        for date_str in dates:
            success = False
            
            for i in range(commit_count):
                file_path = f"streak_updates/{date_str}/{i}.md"
                os.makedirs(os.path.dirname(os.path.join(repo_path, file_path)), exist_ok=True)
                
                content = f"# Update for {date_str}\n\nCommit #{i+1} of {commit_count}\n\nGenerated by GitHub Streak Manager"
                commit_message = f"Update for {date_str} ({i+1}/{commit_count})"
                
                # Add slight delay between commits for more natural behavior
                if i > 0:
                    time.sleep(random.uniform(0.5, 2.0))
                
                success = self.backdate_commit(
                    repo_path=repo_path,
                    date=date_str,
                    commit_message=commit_message,
                    file_content=content,
                    file_path=file_path,
                    push=False  # Don't push individual commits
                )
                
                if not success:
                    break
            
            if success and push:
                try:
                    repo = Repo(repo_path)
                    repo.git.push()
                except Exception as e:
                    print(f"Error pushing commits: {e}")
                    success = False
            
            results[date_str] = success
        
        return results
    
    def fill_missing_streak_dates(self, repo_path: str, days_back: int = 30, push: bool = False) -> Dict[str, bool]:
        """Automatically fill in missing dates in your contribution history.
        
        Args:
            repo_path: Path to local git repository
            days_back: How many days back to analyze and fill
            push: Whether to push the commits to GitHub
            
        Returns:
            Dictionary mapping dates to success status
        """
        # Get streak information
        streak_info = self.analyze_streak()
        
        # Filter missing dates to only include those within days_back
        today = datetime.date.today()
        cutoff_date = (today - datetime.timedelta(days=days_back)).isoformat()
        missing_dates = [date for date in streak_info["missing_dates"] if date >= cutoff_date]
        
        if not missing_dates:
            print("No missing dates found in the specified time range.")
            return {}
        
        # Sort dates chronologically
        missing_dates.sort()
        
        # Create backdated commits for each missing date
        return self.bulk_backdate(
            repo_path=repo_path,
            dates=missing_dates,
            commit_count=random.randint(1, 3),  # Random number of commits for natural appearance
            push=push
        )


def main():
    """Main entry point for the GitHub Streak Manager CLI."""
    parser = argparse.ArgumentParser(description="GitHub Streak Manager")
    
    # Setup subcommand
    parser.add_argument('--setup', action='store_true', help='Set up GitHub credentials')
    parser.add_argument('--token', type=str, help='GitHub Personal Access Token')
    
    # Repository operations
    parser.add_argument('--list-repos', action='store_true', help='List available repositories')
    parser.add_argument('--repo', type=str, help='Repository path to use')
    
    # Commit operations
    parser.add_argument('--date', type=str, help='Date for backdated commit (YYYY-MM-DD)')
    parser.add_argument('--message', type=str, help='Commit message')
    parser.add_argument('--file', type=str, help='File to modify')
    parser.add_argument('--content', type=str, help='Content to write to file')
    parser.add_argument('--push', action='store_true', help='Push commits to GitHub')
    
    # Bulk operations
    parser.add_argument('--bulk', action='store_true', help='Perform bulk backdating')
    parser.add_argument('--start-date', type=str, help='Start date for bulk operation (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date for bulk operation (YYYY-MM-DD)')
    parser.add_argument('--count', type=int, default=1, help='Number of commits per date')
    
    # Analytics
    parser.add_argument('--analyze', action='store_true', help='Analyze current streak')
    parser.add_argument('--username', type=str, help='GitHub username for analysis')
    
    # Auto-fill streak
    parser.add_argument('--fill-streak', action='store_true', help='Automatically fill missing streak dates')
    parser.add_argument('--days-back', type=int, default=30, help='Number of days to look back when filling streak')
    
    args = parser.parse_args()
    
    # Handle setup with skip_token_check
    if args.setup:
        manager = StreakManager(skip_token_check=True)
        manager.setup(args.token)
        return

    manager = StreakManager()
    
    # Handle setup
    if args.setup:
        manager.setup(args.token)
        return
    
    # List repositories
    if args.list_repos:
        repos = manager.suggest_repos()
        print("Available repositories (oldest first):")
        for i, repo in enumerate(repos[:10], 1):
            print(f"{i}. {repo['name']} (Last updated: {repo['updated_at']})")
        return
    
    # Analyze streak
    if args.analyze:
        streak_info = manager.analyze_streak(args.username)
        print(f"Current streak: {streak_info['current_streak']} days")
        print(f"Longest streak: {streak_info['longest_streak']} days")
        print(f"Last commit: {streak_info['last_commit_date']}")
        
        if streak_info['missing_dates']:
            print("Missing dates in your recent history:")
            for date in streak_info['missing_dates'][:10]:  # Show 10 most recent
                print(f"- {date}")
            
            if len(streak_info['missing_dates']) > 10:
                print(f"... and {len(streak_info['missing_dates']) - 10} more")
        return
    
    # Fill streak
    if args.fill_streak and args.repo:
        print(f"Analyzing contribution history and filling missing dates (last {args.days_back} days)...")
        results = manager.fill_missing_streak_dates(args.repo, args.days_back, args.push)
        
        if not results:
            print("✅ Your streak is already complete! No missing dates found.")
            return
            
        successes = sum(1 for success in results.values() if success)
        print(f"Successfully backdated {successes}/{len(results)} missing dates")
        
        if successes > 0 and not args.push:
            print("Note: Commits were not pushed to GitHub. Use --push to push changes.")
        return
    
    # Bulk backdating
    if args.bulk and args.repo and args.start_date and args.end_date:
        start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(args.end_date, "%Y-%m-%d")
        
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current += datetime.timedelta(days=1)
        
        print(f"Bulk backdating {len(dates)} dates from {args.start_date} to {args.end_date}")
        results = manager.bulk_backdate(args.repo, dates, args.count, args.push)
        
        successes = sum(1 for success in results.values() if success)
        print(f"Successfully backdated {successes}/{len(dates)} dates")
        return
    
    # Single backdated commit
    if args.repo and args.date:
        success = manager.backdate_commit(
            repo_path=args.repo,
            date=args.date,
            commit_message=args.message,
            file_content=args.content,
            file_path=args.file,
            push=args.push
        )
        
        if success:
            print(f"✅ Successfully created backdated commit for {args.date}")
            if not args.push:
                print("Note: Commit was not pushed to GitHub. Use --push to push changes.")
        else:
            print("❌ Failed to create backdated commit")
        return
    
    # If no other commands matched, show help
    parser.print_help()


if __name__ == "__main__":
    main()