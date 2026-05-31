import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


IGNORED_BATCH_FOLDERS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
}

IGNORED_SESSION_FILES = {
    ".gitignore",
    "README.md",
}


def run(command, cwd=None):
    print(f"> {' '.join(command)}")
    subprocess.run(command, check=True, cwd=cwd)


def has_staged_changes(folder):
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=folder,
        check=False,
    )
    return result.returncode != 0


def format_number(prefix, number):
    return f"{prefix}{int(number):02d}"


def create_repo_name(exercise, session, course):
    ex = format_number("ex", exercise)
    ss = format_number("ss", session)
    return f"{ex}-{ss}-{course.upper()}"


def slugify(value):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip("-._").lower()
    return slug or "homework"


def create_batch_repo_name(exercise, session, course, folder_name):
    return f"{create_repo_name(exercise, session, course)}-{slugify(folder_name)}"


def create_session_repo_name(file_path, session, course):
    file_name = Path(file_path).stem
    ss = format_number("ss", session)
    return f"{slugify(file_name)}-{ss}-{course.upper()}"


def preview(exercise, session, course):
    repo_name = create_repo_name(exercise, session, course)
    print(repo_name)


def create_readme(exercise, session, course, repo_name, folder=None):
    folder = folder or Path.cwd()
    readme_path = folder / "README.md"

    if readme_path.exists():
        return

    content = f"""# {repo_name}

## Information

- Exercise: EX{int(exercise):02d}
- Session: SS{int(session):02d}
- Course: {course.upper()}

## Description

Homework submission for {course.upper()}.

## How to run

Open `index.html` in your browser.
"""

    readme_path.write_text(content, encoding="utf-8")
    print("Created README.md")


def get_history_file():
    folder = Path.home() / ".homework-repo-tool"
    folder.mkdir(exist_ok=True)
    return folder / "history.json"


def save_history(exercise, session, course, repo_name, repo_url):
    history_file = get_history_file()

    if history_file.exists():
        history = json.loads(history_file.read_text(encoding="utf-8"))
    else:
        history = []

    item = {
        "exercise": f"EX{int(exercise):02d}",
        "session": f"SS{int(session):02d}",
        "course": course.upper(),
        "repo_name": repo_name,
        "repo_url": repo_url,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    history.append(item)

    history_file.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Saved to history")


def show_history():
    history_file = get_history_file()

    if not history_file.exists():
        print("No submission history yet.")
        return

    history = json.loads(history_file.read_text(encoding="utf-8"))

    if not history:
        print("No submission history yet.")
        return

    print("Submitted repositories:")
    print()

    for index, item in enumerate(history, start=1):
        print(f"{index}. {item['exercise']} - {item['session']} - {item['course']}")
        print(f"   Repo: {item['repo_name']}")
        print(f"   Link: {item['repo_url']}")
        print(f"   Time: {item['submitted_at']}")
        print()


def ensure_gitignore(folder):
    gitignore_path = folder / ".gitignore"
    if gitignore_path.exists():
        return

    gitignore_path.write_text(
        "node_modules/\n.env\n.DS_Store\n__pycache__/\n.vscode/\n",
        encoding="utf-8",
    )


def get_github_username():
    return subprocess.check_output(
        ["gh", "api", "user", "--jq", ".login"],
        text=True,
    ).strip()


def github_repo_exists(username, repo_name):
    result = subprocess.run(
        ["gh", "repo", "view", f"{username}/{repo_name}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def set_git_remote(folder, repo_url):
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=folder,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    if result.returncode == 0:
        run(["git", "remote", "set-url", "origin", repo_url], cwd=folder)
    else:
        run(["git", "remote", "add", "origin", repo_url], cwd=folder)


def push_to_github(folder, repo_name, visibility):
    username = get_github_username()
    repo_url = f"https://github.com/{username}/{repo_name}"
    git_url = f"{repo_url}.git"

    if github_repo_exists(username, repo_name):
        print("Repository already exists. Pushing latest files to it...")
    else:
        visibility_flag = "--public" if visibility == "public" else "--private"
        run(["gh", "repo", "create", repo_name, visibility_flag], cwd=folder)

    run(["git", "branch", "-M", "main"], cwd=folder)
    set_git_remote(folder, git_url)
    run(["git", "push", "-u", "origin", "main", "--force"], cwd=folder)

    return repo_url


def submit_folder(
    folder,
    exercise,
    session,
    course,
    visibility,
    repo_name=None,
    include_support_files=True,
):
    folder = folder.resolve()
    repo_name = repo_name or create_repo_name(exercise, session, course)
    print(f"Repo name: {repo_name}")
    print(f"Folder: {folder}")

    if include_support_files:
        create_readme(exercise, session, course, repo_name, folder)

    if not (folder / ".git").exists():
        run(["git", "init"], cwd=folder)

    if include_support_files:
        ensure_gitignore(folder)

    run(["git", "add", "."], cwd=folder)

    if has_staged_changes(folder):
        run(["git", "commit", "-m", f"Submit {repo_name}"], cwd=folder)
    else:
        print("No new changes to commit. Continuing...")

    repo_url = push_to_github(folder, repo_name, visibility)

    save_history(exercise, session, course, repo_name, repo_url)

    print()
    print("Done. Submit this link:")
    print(repo_url)

    return {
        "exercise": f"EX{int(exercise):02d}",
        "file": None,
        "repo_name": repo_name,
        "repo_url": repo_url,
    }


def submit(exercise, session, course, visibility):
    submit_folder(Path.cwd(), exercise, session, course, visibility)


def copy_file_to_temp_folder(source_file, repo_name):
    temp_path = Path(tempfile.mkdtemp())
    repo_folder = temp_path / repo_name
    repo_folder.mkdir()
    shutil.copy2(source_file, repo_folder / source_file.name)
    return temp_path, repo_folder


def submit_single_file(source_file, exercise, session, course, visibility, repo_name=None):
    source_file = Path(source_file)

    if not source_file.exists():
        print(f"File not found: {source_file}")
        return None

    if not source_file.is_file():
        print(f"Not a file: {source_file}")
        return None

    repo_name = repo_name or create_repo_name(exercise, session, course)

    temp_path, folder = copy_file_to_temp_folder(source_file, repo_name)

    try:
        result = submit_folder(
            folder,
            exercise,
            session,
            course,
            visibility,
            repo_name,
            include_support_files=False,
        )
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)

    result["file"] = source_file.name
    return result


def submit_file(file_path, session, course, visibility):
    source_file = Path.cwd() / file_path
    exercise = get_exercise_from_file_name(source_file) or 1
    repo_name = create_session_repo_name(source_file, session, course)
    submit_single_file(source_file, exercise, session, course, visibility, repo_name)


def get_exercise_from_file_name(path):
    match = re.search(r"(\d+)", path.stem)

    if not match:
        return None

    return int(match.group(1))


def find_session_files(folder):
    files = []

    for path in folder.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.name in IGNORED_SESSION_FILES:
            continue
        if path.name.startswith("submission-links-") and path.suffix == ".md":
            continue
        files.append(path)

    return sorted(
        files,
        key=lambda path: (get_exercise_from_file_name(path) or 999999, path.name.lower()),
    )


def build_session_items(session, course):
    files = find_session_files(Path.cwd())
    items = []

    for index, source_file in enumerate(files, start=1):
        exercise = get_exercise_from_file_name(source_file) or index
        items.append(
            {
                "file": source_file,
                "exercise": exercise,
                "repo_name": create_session_repo_name(source_file, session, course),
            }
        )

    return items


def ask_yes_no(question):
    answer = input(f"{question} [Y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def print_session_items(items):
    print("Found files:")
    print()

    for index, item in enumerate(items, start=1):
        print(f"{index}. {item['file'].name} -> {item['repo_name']}")

    print()


def parse_number_selection(selection, max_number):
    numbers = []

    for part in selection.split(","):
        part = part.strip()

        if not part:
            continue

        if not part.isdigit():
            raise ValueError(f"Invalid number: {part}")

        number = int(part)

        if number < 1 or number > max_number:
            raise ValueError(f"Number out of range: {number}")

        if number not in numbers:
            numbers.append(number)

    if not numbers:
        raise ValueError("No files selected")

    return numbers


def choose_session_items(items):
    print_session_items(items)

    if ask_yes_no("Submit all files?"):
        return items

    selection = input("Enter file numbers to submit, separated by comma: ").strip()

    try:
        numbers = parse_number_selection(selection, len(items))
    except ValueError as error:
        print(f"Invalid selection: {error}")
        return []

    selected = [items[number - 1] for number in numbers]

    print()
    print("Selected files:")
    for item in selected:
        print(f"- {item['file'].name} -> {item['repo_name']}")
    print()

    return selected


def session_preview(session, course, visibility):
    items = build_session_items(session, course)

    if not items:
        print("No homework files found in the current folder.")
        return

    print("Repositories will be submitted:")
    print()

    for item in items:
        print(f"{item['file'].name} -> {item['repo_name']}")

    print()

    if ask_yes_no("Do you want to push now?"):
        print()
        submit_session(session, course, visibility)
    else:
        print("Skipped. You can push later with:")
        print(f"hw submit-session {int(session)} {course.upper()}")


def print_submission_summary(submitted, failed):
    if submitted:
        print("Done. Submitted repositories:")
        print()

        for index, item in enumerate(submitted, start=1):
            print(f"{index}. {item['file']}")
            print(f"   Repo: {item['repo_name']}")
            print(f"   Link: {item['repo_url']}")
            print()

        print("Copy these links:")
        print()

        for item in submitted:
            print(item["repo_url"])

    if failed:
        print()
        print("Failed files:")
        for item in failed:
            print(f"- {item['file']}: {item['reason']}")


def write_submission_links(session, course, submitted):
    session_label = f"SS{int(session):02d}"
    output_path = Path.cwd() / f"submission-links-ss{int(session):02d}.md"

    lines = [
        f"# Submission Links - {session_label} - {course.upper()}",
        "",
        "| Exercise | File | Repository | Link |",
        "| -------- | ---- | ---------- | ---- |",
    ]

    for item in submitted:
        lines.append(
            f"| {item['exercise']} | {item['file']} | "
            f"{item['repo_name']} | {item['repo_url']} |"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print()
    print(f"Created {output_path.name}")


def submit_session(session, course, visibility):
    items = build_session_items(session, course)

    if not items:
        print("No homework files found in the current folder.")
        return

    items = choose_session_items(items)

    if not items:
        print("No files submitted.")
        return

    submitted = []
    failed = []

    for item in items:
        source_file = item["file"]
        exercise = item["exercise"]
        repo_name = item["repo_name"]

        print("=" * 60)
        print(f"Submitting {source_file.name}")
        print("=" * 60)

        try:
            result = submit_single_file(
                source_file,
                exercise,
                session,
                course,
                visibility,
                repo_name,
            )
            if result:
                submitted.append(result)
            else:
                failed.append({"file": source_file.name, "reason": "Submit skipped"})
        except subprocess.CalledProcessError as error:
            failed.append({"file": source_file.name, "reason": str(error)})
            print(f"Failed to submit {source_file.name}. Continuing...")

        print()

    if submitted:
        write_submission_links(session, course, submitted)

    print_submission_summary(submitted, failed)


def find_homework_folders(root):
    folders = []

    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_dir():
            continue
        if path.name.startswith(".") or path.name in IGNORED_BATCH_FOLDERS:
            continue
        folders.append(path)

    return folders


def batch_preview(exercise, session, course):
    folders = find_homework_folders(Path.cwd())

    if not folders:
        print("No homework folders found.")
        return

    print("Repositories will be created:")
    print()

    for folder in folders:
        repo_name = create_batch_repo_name(exercise, session, course, folder.name)
        print(f"- {folder.name} -> {repo_name}")


def batch_submit(exercise, session, course, visibility):
    folders = find_homework_folders(Path.cwd())

    if not folders:
        print("No homework folders found.")
        return

    print(f"Found {len(folders)} homework folder(s).")
    print()

    submitted = []
    failed = []

    for folder in folders:
        repo_name = create_batch_repo_name(exercise, session, course, folder.name)
        print("=" * 60)
        print(f"Submitting {folder.name}")
        print("=" * 60)

        try:
            submit_folder(folder, exercise, session, course, visibility, repo_name)
            submitted.append(repo_name)
        except subprocess.CalledProcessError as error:
            failed.append((repo_name, error))
            print(f"Failed to submit {repo_name}. Continuing...")

        print()

    print("Batch submit finished.")
    print(f"Submitted: {len(submitted)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print()
        print("Failed repositories:")
        for repo_name, _ in failed:
            print(f"- {repo_name}")


def main():
    parser = argparse.ArgumentParser(description="Homework GitHub repo submitter")

    subparsers = parser.add_subparsers(dest="command")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("exercise")
    preview_parser.add_argument("session")
    preview_parser.add_argument("course")

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("exercise")
    submit_parser.add_argument("session")
    submit_parser.add_argument("course")
    submit_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    submit_file_parser = subparsers.add_parser("submit-file")
    submit_file_parser.add_argument("file")
    submit_file_parser.add_argument("session")
    submit_file_parser.add_argument("course")
    submit_file_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    submit_session_parser = subparsers.add_parser("submit-session")
    submit_session_parser.add_argument("session")
    submit_session_parser.add_argument("course")
    submit_session_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    session_preview_parser = subparsers.add_parser("session-preview")
    session_preview_parser.add_argument("session")
    session_preview_parser.add_argument("course")
    session_preview_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    batch_preview_parser = subparsers.add_parser("batch-preview")
    batch_preview_parser.add_argument("exercise")
    batch_preview_parser.add_argument("session")
    batch_preview_parser.add_argument("course")

    batch_submit_parser = subparsers.add_parser("batch-submit")
    batch_submit_parser.add_argument("exercise")
    batch_submit_parser.add_argument("session")
    batch_submit_parser.add_argument("course")
    batch_submit_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    subparsers.add_parser("history")

    args = parser.parse_args()

    if args.command == "preview":
        preview(args.exercise, args.session, args.course)
    elif args.command == "submit":
        submit(args.exercise, args.session, args.course, args.visibility)
    elif args.command == "submit-file":
        submit_file(args.file, args.session, args.course, args.visibility)
    elif args.command == "submit-session":
        submit_session(args.session, args.course, args.visibility)
    elif args.command == "session-preview":
        session_preview(args.session, args.course, args.visibility)
    elif args.command == "batch-preview":
        batch_preview(args.exercise, args.session, args.course)
    elif args.command == "batch-submit":
        batch_submit(args.exercise, args.session, args.course, args.visibility)
    elif args.command == "history":
        show_history()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
