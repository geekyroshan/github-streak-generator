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
    
    def _generate_commit_message(self, date_str=None, file_path=None, commit_index=0, total_commits=1) -> str:
        """Generate a realistic commit message based on context.
        
        Args:
            date_str: The date of the commit (for context)
            file_path: Path to the file being modified
            commit_index: Index of the current commit (0-based)
            total_commits: Total number of commits for this date
            
        Returns:
            A contextually appropriate commit message
        """
        # For first commits in a repository
        if commit_index == 0 and total_commits > 1:
            initial_messages = [
                "Initial commit",
                "Initialize project structure",
                "Setup project boilerplate",
                "First commit",
                "Create basic project structure",
                "Start new project",
                "Set up repository"
            ]
            return random.choice(initial_messages)
        
        # For documentation updates
        if file_path and ("README" in file_path or "docs/" in file_path or ".md" in file_path):
            doc_messages = [
                "Update documentation",
                "Improve README clarity",
                "Add installation instructions",
                "Update usage examples",
                "Fix typo in documentation",
                "Add section on advanced usage",
                "Document new feature",
                "Update API documentation",
                "Add contributing guidelines",
                "Update changelog"
            ]
            return random.choice(doc_messages)
        
        # For final commits in a series
        if commit_index == total_commits - 1 and total_commits > 1:
            final_messages = [
                "Final adjustments",
                "Clean up code before pushing",
                "Fix minor issues",
                "Apply code review feedback",
                "Prepare for deployment",
                "Ready for release",
                "Final tweaks before merge"
            ]
            return random.choice(final_messages)
        
        # General coding messages
        code_messages = [
            "Update functionality",
            "Refactor code for better readability",
            "Optimize performance",
            "Fix bug in error handling",
            "Improve code structure",
            "Add new feature",
            "Fix edge case",
            "Implement requested changes",
            "Clean up code formatting",
            "Improve error messages",
            "Add better comments",
            "Refactor utility functions",
            "Remove deprecated code",
            "Add unit tests",
            "Fix linting issues",
            "Improve logging",
            "Update dependencies",
            "Add error handling",
            "Implement feedback from code review",
            "Fix security vulnerability",
            "Update API endpoint",
            "Add new helper method",
            "Make code more maintainable",
            "Simplify complex logic",
            "Fix regression"
        ]
        return random.choice(code_messages)
    
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
            commit_count: Number of commits per date (or max if randomized)
            push: Whether to push the commits to GitHub
            
        Returns:
            Dictionary mapping dates to success status
        """
        results = {}
        
        # Get weekdays for each date to make patterns more realistic
        date_info = {}
        for date_str in dates:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            is_weekend = dt.weekday() >= 5  # 5 = Saturday, 6 = Sunday
            day_of_week = dt.weekday()
            
            # Randomize commit count based on weekday/weekend for more realistic patterns
            # Weekends typically have fewer commits
            if commit_count == 1:
                # Default behavior, 1 commit
                actual_commit_count = 1
            else:
                # More realistic pattern: more commits on weekdays (especially midweek), fewer on weekends
                if is_weekend:
                    # Weekend: 0-2 commits usually
                    actual_commit_count = random.choices(
                        [0, 1, 2], 
                        weights=[30, 60, 10],  # 30% chance of 0, 60% chance of 1, 10% chance of 2
                        k=1
                    )[0]
                else:
                    # Weekday: Distribution based on day of week
                    # Monday/Friday: 1-3 commits typically
                    # Tuesday-Thursday: 1-5 commits typically
                    if day_of_week in [0, 4]:  # Monday or Friday
                        max_count = min(3, commit_count)
                        weights = [0, 40, 40, 20]  # 0, 1, 2, 3 commits
                    else:  # Tuesday, Wednesday, Thursday
                        max_count = min(5, commit_count)
                        weights = [0, 20, 30, 30, 15, 5]  # 0, 1, 2, 3, 4, 5 commits
                    
                    # Adjust weights array to match the max count
                    weights = weights[:max_count+1]
                    # Ensure weights sum to 100
                    total = sum(weights)
                    weights = [w * 100 / total for w in weights]
                    
                    # Ensure the population and weights arrays match in length
                    population = list(range(max_count + 1))
                    if len(population) != len(weights):
                        # Trim or extend weights to match population length
                        if len(weights) > len(population):
                            weights = weights[:len(population)]
                        else:
                            weights.extend([1] * (len(population) - len(weights)))
                        # Normalize weights again
                        total = sum(weights)
                        weights = [w * 100 / total for w in weights]
                    
                    actual_commit_count = random.choices(
                        population,
                        weights=weights,
                        k=1
                    )[0]
            
            date_info[date_str] = {
                'weekday': day_of_week,
                'is_weekend': is_weekend,
                'commit_count': actual_commit_count
            }
        
        for date_str in dates:
            success = False
            actual_commit_count = date_info[date_str]['commit_count']
            
            # Skip dates with 0 commits (for natural pattern)
            if actual_commit_count == 0:
                print(f"Skipping {date_str} (no commits scheduled)")
                results[date_str] = True
                continue
            
            print(f"Creating {actual_commit_count} commits for {date_str}")
            
            # Different file types for variety
            file_types = [
                "docs/updates.md",
                "src/main.py",
                "utils/helpers.py",
                "config/settings.json",
                "README.md",
                "tests/test_main.py",
                "data/sample.json"
            ]
            
            # Choose random subset of files to modify for this date
            daily_files = random.sample(file_types, min(actual_commit_count, len(file_types)))
            if actual_commit_count > len(daily_files):
                # Add repeats if needed
                daily_files.extend(random.sample(file_types, actual_commit_count - len(daily_files)))
            
            for i in range(actual_commit_count):
                # Pick a file to modify
                file_type = daily_files[i]
                file_path = f"streak_updates/{date_str}/{file_type}"
                
                # Create content based on file type
                if file_path.endswith('.md'):
                    content = f"# Update for {date_str}\n\nDocumentation update #{i+1}.\n\n## Changes\n\n- Updated documentation\n- Improved examples\n- Fixed typos"
                elif file_path.endswith('.py'):
                    content = f'''"""
Module updated on {date_str}
"""

def sample_function_{date_str.replace("-", "")}_{i}():
    """Example function added in update #{i+1}."""
    print("Sample function implementation")
    return True

# Added in update #{i+1}
class SampleClass:
    """Example class for demonstration."""
    
    def __init__(self):
        """Initialize the class."""
        self.value = "{date_str}"
    
    def get_value(self):
        """Return the stored value."""
        return self.value
'''
                elif file_path.endswith('.json'):
                    content = f'''{{
  "update_date": "{date_str}",
  "update_number": {i+1},
  "changes": [
    "Updated configuration",
    "Modified settings",
    "Adjusted parameters"
  ]
}}'''
                else:
                    content = f"# Update for {date_str}\n\nCommit #{i+1} of {actual_commit_count}\n\nGenerated content for file type: {file_path.split('.')[-1]}"
                
                # Generate appropriate commit message for context
                commit_message = self._generate_commit_message(
                    date_str=date_str,
                    file_path=file_path,
                    commit_index=i,
                    total_commits=actual_commit_count
                )
                
                # Add variable delay between commits for more natural behavior
                if i > 0:
                    # More natural pause between commits (people typically don't commit every few seconds)
                    time.sleep(random.uniform(1.0, 5.0))
                
                # Create the commit with a random time during work hours
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
            
            if success and push and actual_commit_count > 0:
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
        
        # Calculate a realistic maximum number of commits per day
        # Most developers don't have more than 5-10 commits per day on average
        max_commits = random.randint(5, 10)
        
        print(f"Found {len(missing_dates)} missing dates in contribution history.")
        print(f"Will create varied commit patterns (up to {max_commits} commits per day) to look natural.")
        
        # Create backdated commits for each missing date with varied pattern
        return self.bulk_backdate(
            repo_path=repo_path,
            dates=missing_dates,
            commit_count=max_commits,  # This is now used as a maximum, actual count will vary
            push=push
        )
    
    def create_natural_streak_pattern(self, 
                               repo_path: str, 
                               start_date: str, 
                               end_date: str, 
                               reference_username: Optional[str] = None,
                               max_daily_commits: int = 8,
                               push: bool = False) -> Dict[str, bool]:
        """Create a natural looking streak pattern, optionally based on a reference user.
        
        This creates a more realistic commit pattern that follows typical developer habits:
        - Less activity on weekends
        - Variable number of commits per day
        - Occasional days with no commits
        - More activity during standard work hours
        - Realistic commit messages based on file types
        
        Args:
            repo_path: Path to local git repository
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            reference_username: Optional GitHub username to analyze for pattern reference
            max_daily_commits: Maximum number of commits per day
            push: Whether to push the commits to GitHub
            
        Returns:
            Dictionary mapping dates to success status
        """
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        
        # Generate list of dates
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current += datetime.timedelta(days=1)
        
        # If reference username provided, analyze their pattern
        activity_pattern = {}
        if reference_username:
            try:
                print(f"Analyzing commit pattern of GitHub user: {reference_username}")
                streak_info = self.analyze_streak(reference_username)
                
                # Use the contribution_days to identify active/inactive days
                contribution_days = streak_info.get("contribution_days", [])
                
                # Map day of week to activity levels based on reference user
                day_of_week_activity = [0, 0, 0, 0, 0, 0, 0]  # Sun-Sat
                day_of_week_count = [0, 0, 0, 0, 0, 0, 0]
                
                for day in contribution_days:
                    date = datetime.datetime.strptime(day["date"], "%Y-%m-%d")
                    day_index = date.weekday()
                    contribution_count = day["count"]
                    
                    day_of_week_activity[day_index] += contribution_count
                    day_of_week_count[day_index] += 1
                
                # Calculate average commits per day of week
                for i in range(7):
                    if day_of_week_count[i] > 0:
                        day_of_week_activity[i] /= day_of_week_count[i]
                    # Cap at max_daily_commits
                    day_of_week_activity[i] = min(day_of_week_activity[i], max_daily_commits)
                
                print(f"Reference user activity pattern per day of week:")
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                for i in range(7):
                    print(f"  {days[i]}: {day_of_week_activity[i]:.1f} commits on average")
                
                activity_pattern = {
                    "day_of_week_activity": day_of_week_activity
                }
                
            except Exception as e:
                print(f"Error analyzing reference user: {e}")
                print("Using default activity pattern.")
                activity_pattern = {}
        
        # Apply the pattern to generate a realistic streak
        # We'll do this by modifying the dates list to set commit counts
        dates_with_metadata = []
        
        for date_str in dates:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            day_of_week = dt.weekday()  # 0-6 (Mon-Sun)
            
            if activity_pattern and "day_of_week_activity" in activity_pattern:
                # Use reference user's pattern
                avg_commits = activity_pattern["day_of_week_activity"][day_of_week]
                
                # Add some randomness around the average
                # For smaller numbers (0-2), keep it precise
                # For larger numbers, add more variation
                if avg_commits < 1:
                    # Mostly 0, occasionally 1
                    commit_count = random.choices([0, 1], weights=[80, 20], k=1)[0]
                elif avg_commits < 2:
                    # Mix of 0, 1, and occasionally 2
                    commit_count = random.choices([0, 1, 2], weights=[20, 60, 20], k=1)[0]
                else:
                    # Normal distribution around the average
                    variance = max(1, avg_commits / 2)
                    commit_count = int(random.normalvariate(avg_commits, variance))
                    commit_count = max(0, min(commit_count, max_daily_commits))
            else:
                # Default pattern based on typical work week
                is_weekend = day_of_week >= 5
                
                if is_weekend:
                    # Weekends have fewer commits
                    commit_count = random.choices(
                        [0, 1, 2], 
                        weights=[50, 40, 10],  # 50% chance of 0, 40% chance of 1, 10% chance of 2
                        k=1
                    )[0]
                else:
                    # Workdays have more commits, with variance by day
                    # Monday and Friday less active than midweek
                    if day_of_week in [0, 4]:  # Monday or Friday
                        max_count = max_daily_commits - 2
                        weights = [10, 30, 40, 15, 5]  # 0, 1, 2, 3, 4
                    else:  # Tuesday, Wednesday, Thursday
                        max_count = max_daily_commits
                        weights = [5, 15, 30, 25, 15, 5, 3, 2]  # 0-7
                    
                    # Adjust weights array to match the max count
                    weights = weights[:max_count + 1]
                    # Ensure weights sum to 100
                    total = sum(weights)
                    weights = [w * 100 / total for w in weights]
                    
                    # Ensure the population and weights arrays match in length
                    population = list(range(max_count + 1))
                    if len(population) != len(weights):
                        # Trim or extend weights to match population length
                        if len(weights) > len(population):
                            weights = weights[:len(population)]
                        else:
                            weights.extend([1] * (len(population) - len(weights)))
                        # Normalize weights again
                        total = sum(weights)
                        weights = [w * 100 / total for w in weights]
                    
                    commit_count = random.choices(
                        population,
                        weights=weights,
                        k=1
                    )[0]
                        
            dates_with_metadata.append({
                "date": date_str,
                "commit_count": commit_count
            })
            
        # Summarize the generated pattern
        active_days = sum(1 for d in dates_with_metadata if d["commit_count"] > 0)
        total_commits = sum(d["commit_count"] for d in dates_with_metadata)
        
        print(f"Generated natural streak pattern from {start_date} to {end_date}:")
        print(f"  - {len(dates)} total days, {active_days} active days ({active_days/len(dates)*100:.1f}%)")
        print(f"  - {total_commits} total commits, {total_commits/len(dates):.1f} commits per day average")
        
        # Create the commits based on pattern
        filtered_dates = [d["date"] for d in dates_with_metadata if d["commit_count"] > 0]
        commit_counts = {d["date"]: d["commit_count"] for d in dates_with_metadata if d["commit_count"] > 0}
        
        # Process each date for creation
        results = {}
        
        for date_str in filtered_dates:
            commit_count = commit_counts[date_str]
            print(f"Creating {commit_count} commits for {date_str}")
            
            # Different file types for variety
            file_types = [
                "docs/updates.md",
                "src/main.py",
                "utils/helpers.py",
                "config/settings.json",
                "README.md",
                "tests/test_main.py",
                "data/sample.json"
            ]
            
            # Choose random subset of files to modify for this date
            daily_files = random.sample(file_types, min(commit_count, len(file_types)))
            if commit_count > len(daily_files):
                # Add repeats if needed
                daily_files.extend(random.sample(file_types, commit_count - len(daily_files)))
            
            success = False
            
            for i in range(commit_count):
                # Pick a file to modify
                file_type = daily_files[i]
                file_path = f"streak_updates/{date_str}/{file_type}"
                
                # Create content based on file type
                if file_path.endswith('.md'):
                    content = f"# Update for {date_str}\n\nDocumentation update #{i+1}.\n\n## Changes\n\n- Updated documentation\n- Improved examples\n- Fixed typos"
                elif file_path.endswith('.py'):
                    content = f'''"""
Module updated on {date_str}
"""

def sample_function_{date_str.replace("-", "")}_{i}():
    """Example function added in update #{i+1}."""
    print("Sample function implementation")
    return True

# Added in update #{i+1}
class SampleClass:
    """Example class for demonstration."""
    
    def __init__(self):
        """Initialize the class."""
        self.value = "{date_str}"
    
    def get_value(self):
        """Return the stored value."""
        return self.value
'''
                elif file_path.endswith('.json'):
                    content = f'''{{
  "update_date": "{date_str}",
  "update_number": {i+1},
  "changes": [
    "Updated configuration",
    "Modified settings",
    "Adjusted parameters"
  ]
}}'''
                else:
                    content = f"# Update for {date_str}\n\nCommit #{i+1} of {commit_count}\n\nGenerated content for file type: {file_path.split('.')[-1]}"
                
                # Generate appropriate commit message for context
                commit_message = self._generate_commit_message(
                    date_str=date_str,
                    file_path=file_path,
                    commit_index=i,
                    total_commits=commit_count
                )
                
                # Add variable delay between commits for more natural behavior
                if i > 0:
                    # More natural pause between commits
                    time.sleep(random.uniform(1.0, 5.0))
                
                # Create the commit with a random time during work hours
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
            
        # Final statistics
        successful_days = sum(1 for success in results.values() if success)
        print(f"\nStreak creation complete: {successful_days}/{len(filtered_dates)} days successfully processed")
        
        return results


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
    
    # Natural streak pattern
    parser.add_argument('--natural-pattern', action='store_true', 
                       help='Create a natural-looking commit pattern with realistic activity')
    parser.add_argument('--reference-user', type=str,
                       help='GitHub username to analyze and mimic their commit pattern')
    parser.add_argument('--max-daily-commits', type=int, default=8,
                       help='Maximum number of commits for any given day')
    
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
    
    # Create natural streak pattern
    if args.natural_pattern and args.repo and args.start_date and args.end_date:
        print(f"Creating natural commit streak pattern from {args.start_date} to {args.end_date}")
        print(f"Repository: {args.repo}")
        
        if args.reference_user:
            print(f"Using {args.reference_user}'s commit pattern as reference")
        
        results = manager.create_natural_streak_pattern(
            repo_path=args.repo,
            start_date=args.start_date,
            end_date=args.end_date,
            reference_username=args.reference_user,
            max_daily_commits=args.max_daily_commits,
            push=args.push
        )
        
        # Success statistics already printed in the function
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