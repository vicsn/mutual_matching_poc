# Algorand Mutual Matching Demo

*This demo is based on the Algorand Auction Demo*

## Usage

The file `mutual_matching/operations.py` provides a set of functions that can be used to create and interact
with the mutual_matching contract. See that file for documentation.

## Development Setup

This repo requires Python 3.6 or higher. We recommend you use a Python virtual environment to install
the required dependencies.

Set up venv (one time):
 * `python3 -m venv venv`

Active venv:
 * `. venv/bin/activate` (if your shell is bash/zsh)
 * `. venv/bin/activate.fish` (if your shell is fish)

Install dependencies:
* `pip install -r requirements.txt`

Run example:
* First, start an instance of [sandbox](https://github.com/algorand/sandbox) (requires Docker): `./sandbox up nightly`
* `python3 example_mutual_matching.py`
* When finished, the sandbox can be stopped with `./sandbox down`

Format code:
* `black .`
