from setuptools import setup, find_packages

setup(
    name="github_streak_manager",
    version="0.1.0",
    description="A tool to maintain GitHub contribution streaks",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "GitPython>=3.1.0",
        "schedule>=1.1.0",
        "python-daemon>=2.3.0;platform_system!='Windows'",
    ],
    entry_points={
        "console_scripts": [
            "github-streak-manager=github_streak_manager.main:main",
            "github-streak-scheduler=github_streak_manager.scheduler:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.7",
)