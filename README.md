# Homework Repo Tool

Homework Repo Tool is a Python CLI for submitting homework files to GitHub.

It can scan a session folder, preview repositories, detect project folders (FastAPI / web / Node), and submit homework safely with `.gitignore`, dry-run, and config defaults.

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

## Quick start

```bash
hw
```

Gõ `hw` (không kèm lệnh) sẽ mở **menu tương tác** — chọn số là dùng được.

Hoặc:

```bash
hw menu
hw doctor
hw config set default_course it205
hw plan
```

## Commands

### Session (one file = one repo)

Preview:

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

### Projects (FastAPI / web / many files = one repo)

```bash
hw up-project todo-api
hw up-project todo-api --name todo-api-ss05
hw up-project todo-api --dry-run
```

### Folders

Current folder with custom repo name:

```bash
hw up hackathon-team-01
```

Whole folder as one repository:

```bash
hw up-session bai3-4
```

Each top-level file/folder as its own repository:

```bash
hw up-folder ss05
```

### Plan before submit

```bash
hw plan
hw plan ss05
```

Shows whether each item is treated as:

- `file` → one file, one repo
- `folder` → folder upload
- `project` → multi-file app (requirements.txt, package.json, app/, ...)

### Safety flags

```bash
hw up-project app --dry-run      # preview only
hw submit-session 5 it205 --yes  # skip prompts
hw up-project app --overwrite    # force push if repo exists
hw submit-session 5 it205 --visibility private
```

### Config

```bash
hw config
hw config set default_course it205
hw config set default_visibility public
hw config set naming "{name}-ss{session:02d}-{course}"
```

Config file: `~/.homework-repo-tool/config.json`

### History

```bash
hw history
hw history --course it205
hw history --session 5 --limit 10
```

### Doctor / Guide

```bash
hw doctor
hw guide
```

## Safety features

- Blocks `.env`, `venv/`, `node_modules/`, `__pycache__/`, secrets-like files
- Auto `.gitignore` by stack: `python` / `node` / `web`
- README template by stack (FastAPI / Node / HTML)
- No force push by default (use `--overwrite`)
- Dry-run mode for safe preview

## Topics

Submitted repositories are tagged automatically when session/course are known:

```text
homework
it205
ss05
```
