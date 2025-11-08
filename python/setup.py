"""
Setup script for Renko Trend Following Strategy

Install with:
    pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="renko-trend-following",
    version="1.0.0",
    author="Renko Trend Following Strategy",
    description="Complete Python implementation of Renko Trend Following trading strategy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/renko-trend-following",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "matplotlib>=3.7.0",
    ],
    extras_require={
        "data": ["yfinance>=0.2.0"],
        "notebook": ["jupyter>=1.0.0", "notebook>=7.0.0", "ipywidgets>=8.0.0"],
        "viz": ["plotly>=5.14.0", "seaborn>=0.12.0"],
        "dev": ["pytest>=7.0.0", "black>=23.0.0", "flake8>=6.0.0", "mypy>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "renko-backtest=main:main",
        ],
    },
)
