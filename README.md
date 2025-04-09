# GitHub Streak Manager

A tool to help maintain your GitHub contribution streak by managing backdated commits and automated repository updates.

## Installation

```bash
# Clone the repository
git clone https://github.com/roshankharel/github-streak-manager.git
cd github-streak-manager

# Set up a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package and dependencies
pip install -e .
```

### Required Dependencies

This tool requires the following packages, which will be installed automatically when you run `pip install -e .`:

- `requests`: For GitHub API communication
- `GitPython`: For git operations
- `schedule`: For scheduling automated commits
- `python-daemon`: For daemon processes (Linux/Mac only)

## Setup

Before using the GitHub Streak Manager, you need to set up your GitHub Personal Access Token:

```bash
github-streak-manager --setup
```

When prompted, enter your GitHub Personal Access Token. You can generate a new token at [GitHub Developer Settings](https://github.com/settings/tokens) with the `repo` scope.

## Usage

### List Your Repositories

```bash
github-streak-manager --list-repos
```

### Create a Backdated Commit

```bash
github-streak-manager --repo /path/to/local/repo --date 2023-10-01 --push
```

### Bulk Backdating

Create commits for a range of dates:

```bash
github-streak-manager --bulk --repo /path/to/local/repo --start-date 2023-09-01 --end-date 2023-09-30 --count 2 --push
```

### Create a Natural-Looking Commit Pattern

Create a realistic commit pattern that mimics typical developer behavior (varied commit counts, fewer weekend commits, etc.):

```bash
github-streak-manager --natural-pattern --repo /path/to/local/repo --start-date 2023-09-01 --end-date 2023-12-31 --push
```

You can even mimic another GitHub user's commit pattern:

```bash
github-streak-manager --natural-pattern --repo /path/to/local/repo --start-date 2023-09-01 --end-date 2023-12-31 --reference-user popular-developer --push
```

Control the maximum number of commits per day:

```bash
github-streak-manager --natural-pattern --repo /path/to/local/repo --start-date 2023-09-01 --end-date 2023-12-31 --max-daily-commits 5 --push
```

### Analyze Your Streak

```bash
github-streak-manager --analyze
```

### Automatically Fill Missing Streak Dates

Fill in any missing dates in your contribution history from the past 30 days:

```bash
github-streak-manager --fill-streak --repo /path/to/local/repo --push
```

You can specify how far back to look:

```bash
github-streak-manager --fill-streak --repo /path/to/local/repo --days-back 60 --push
```

### Automated Streak Maintenance with Scheduler

The GitHub Streak Manager includes a scheduler that can automatically maintain your streak by creating a commit each day if you haven't made any contributions yet.

Run the scheduler:

```bash
github-streak-scheduler --repo /path/to/local/repo
```

Schedule at a specific time (24-hour format):

```bash
github-streak-scheduler --repo /path/to/local/repo --hour 16 --minute 30
```

Run as a daemon process in the background (Linux/Mac only):

```bash
github-streak-scheduler --repo /path/to/local/repo --daemon
```

## Advanced Options

- `--message "Your commit message"`: Custom commit message
- `--file "path/to/file"`: Specify which file to modify
- `--content "New content"`: Specify the content to write to the file
- `--count 3`: Number of commits per date for bulk operations

## Ethical Usage

This tool is intended for legitimate use cases, such as:
- Pushing work that you completed offline
- Maintaining visibility for projects you're actively working on
- Ensuring your GitHub profile accurately reflects your development activity

Please use this tool responsibly and in accordance with GitHub's Terms of Service.

## License

MIT


