# Homework Repo Tool

Homework Repo Tool is a Python CLI for submitting homework files to GitHub.

It can scan a session folder, preview the repositories that will be created, and submit each Python exercise file as a separate GitHub repository.
The terminal output uses tables and panels for easier reading.

## Requirements

- Python 3.9 or newer
- Git
- GitHub CLI
- pipx

Login to GitHub CLI before submitting:

```bash
gh auth login
```

## Install For Development

From this project folder:

```bash
pipx install -e .
```

If already installed and you changed the code:

```bash
pipx reinstall homework-repo-tool
```

## Usage

Preview a session:

```bash
hw session-preview 5 it205
```

Submit a session:

```bash
hw submit-session 5 it205
```

Submit one file:

```bash
hw submit-file bai1.py 5 it205
```

Show history:

```bash
hw history
```

Check whether your machine is ready:

```bash
hw doctor
```

By default, repositories are public. To create private repositories:

```bash
hw submit-session 5 it205 --visibility private
```

Submitted repositories are tagged automatically with topics like:

```text
homework
it205
ss05
```
