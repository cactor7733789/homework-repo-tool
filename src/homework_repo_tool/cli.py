import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    def _strip_markup(value):
        return re.sub(r"\[/?[^\]]+\]", "", str(value))


    class Console:
        def print(self, *values, **kwargs):
            if not values:
                print()
                return

            print(*(_strip_markup(value) for value in values))

        def rule(self, title):
            print()
            print(f"--- {title} ---")


    class Panel:
        def __init__(self, renderable, title=None, border_style=None):
            self.renderable = renderable
            self.title = title

        def __str__(self):
            if self.title:
                return f"{self.title}\n{self.renderable}"
            return str(self.renderable)


    class Table:
        def __init__(self, title=None):
            self.title = title
            self.columns = []
            self.rows = []

        def add_column(self, header, **kwargs):
            self.columns.append(header)

        def add_row(self, *values):
            self.rows.append([str(value) for value in values])

        def __str__(self):
            lines = []

            if self.title:
                lines.append(self.title)

            if self.columns:
                lines.append(" | ".join(self.columns))
                lines.append(" | ".join("-" * len(column) for column in self.columns))

            for row in self.rows:
                lines.append(" | ".join(row))

            return "\n".join(lines)


console = Console()


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


class SubmissionSkipped(Exception):
    pass


def run(command, cwd=None):
    console.print(f"[dim]> {' '.join(command)}[/dim]")
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


def create_repo_topics(session, course):
    return ["homework", slugify(course), format_number("ss", session)]


def preview(exercise, session, course):
    repo_name = create_repo_name(exercise, session, course)
    console.print(Panel(repo_name, title="Repository name", border_style="cyan"))


def create_readme(exercise, session, course, repo_name, folder=None):
    folder = folder or Path.cwd()
    readme_path = folder / "README.md"

    if readme_path.exists():
        return

    info_lines = []
    if exercise is not None:
        info_lines.append(f"- Exercise: EX{int(exercise):02d}")
    if session is not None:
        info_lines.append(f"- Session: SS{int(session):02d}")
    if course:
        info_lines.append(f"- Course: {course.upper()}")

    if info_lines:
        info_section = "## Information\n\n" + "\n".join(info_lines) + "\n\n"
    else:
        info_section = ""

    course_label = course.upper() if course else "this course"
    content = (
        f"# {repo_name}\n\n"
        f"{info_section}"
        "## Description\n\n"
        f"Homework submission for {course_label}.\n\n"
        "## How to run\n\n"
        "Open `index.html` in your browser.\n"
    )

    readme_path.write_text(content, encoding="utf-8")
    console.print("[green]Created README.md[/green]")


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

    exercise_label = f"EX{int(exercise):02d}" if exercise is not None else "-"
    session_label = f"SS{int(session):02d}" if session is not None else "-"
    course_label = course.upper() if course else "-"

    item = {
        "exercise": exercise_label,
        "session": session_label,
        "course": course_label,
        "repo_name": repo_name,
        "repo_url": repo_url,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    history.append(item)

    history_file.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    console.print("[green]Saved to history[/green]")


def show_history():
    history_file = get_history_file()

    if not history_file.exists():
        console.print("[yellow]No submission history yet.[/yellow]")
        return

    history = json.loads(history_file.read_text(encoding="utf-8"))

    if not history:
        console.print("[yellow]No submission history yet.[/yellow]")
        return

    table = Table(title="Submitted repositories")
    table.add_column("No", justify="right")
    table.add_column("Exercise")
    table.add_column("Session")
    table.add_column("Course")
    table.add_column("Repository")
    table.add_column("Link")
    table.add_column("Time")

    for index, item in enumerate(history, start=1):
        table.add_row(
            str(index),
            item["exercise"],
            item["session"],
            item["course"],
            item["repo_name"],
            item["repo_url"],
            item["submitted_at"],
        )

    console.print(table)


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


def add_repo_topics(username, repo_name, session, course):
    if session is None or not course:
        return

    topics = create_repo_topics(session, course)
    command = ["gh", "repo", "edit", f"{username}/{repo_name}"]

    for topic in topics:
        command.extend(["--add-topic", topic])

    result = subprocess.run(command, check=False)

    if result.returncode == 0:
        console.print(f"[green]Added topics:[/green] {', '.join(topics)}")
    else:
        console.print("[yellow]Could not add repository topics. Continuing...[/yellow]")


def push_to_github(folder, repo_name, visibility, session, course):
    username = get_github_username()
    repo_url = f"https://github.com/{username}/{repo_name}"
    git_url = f"{repo_url}.git"

    if github_repo_exists(username, repo_name):
        if not ask_yes_no(f"Repository {repo_name} already exists. Overwrite it?"):
            raise SubmissionSkipped(f"Skipped existing repository: {repo_name}")
        console.print("[yellow]Repository already exists. Pushing latest files to it...[/yellow]")
    else:
        visibility_flag = "--public" if visibility == "public" else "--private"
        run(["gh", "repo", "create", repo_name, visibility_flag], cwd=folder)

    run(["git", "branch", "-M", "main"], cwd=folder)
    set_git_remote(folder, git_url)
    run(["git", "push", "-u", "origin", "main", "--force"], cwd=folder)
    add_repo_topics(username, repo_name, session, course)

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
    console.print(f"[bold]Repo name:[/bold] {repo_name}")
    console.print(f"[bold]Folder:[/bold] {folder}")

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
        console.print("[yellow]No new changes to commit. Continuing...[/yellow]")

    repo_url = push_to_github(folder, repo_name, visibility, session, course)

    save_history(exercise, session, course, repo_name, repo_url)

    console.print()
    console.print(Panel(repo_url, title="Done. Submit this link", border_style="green"))

    return {
        "exercise": f"EX{int(exercise):02d}" if exercise is not None else "-",
        "file": None,
        "repo_name": repo_name,
        "repo_url": repo_url,
    }


def submit(exercise, session, course, visibility):
    try:
        submit_folder(Path.cwd(), exercise, session, course, visibility)
    except SubmissionSkipped as error:
        print(error)

def up(repo_name, visibility):
    repo_name = str(repo_name).strip()

    if not repo_name:
        console.print("[red]Repository name is required.[/red]")
        return

    if not re.fullmatch(r"[A-Za-z0-9._-]+", repo_name):
        console.print(
            "[yellow]Warning:[/yellow] Repo name may be invalid on GitHub. "
            "Use only letters, numbers, dot (.), underscore (_), hyphen (-)."
        )

    source_files = find_session_files(Path.cwd())
    if not source_files:
        console.print("[yellow]No homework files found in the current folder.[/yellow]")
        return

    table = Table(title=f"Found {len(source_files)} file(s)")
    table.add_column("No", justify="right", style="cyan")
    table.add_column("File", style="bold")
    table.add_column("Repository", style="green")

    for index, source_file in enumerate(source_files, start=1):
        table.add_row(str(index), source_file.name, repo_name)

    console.print(table)

    if not ask_yes_no("Do you want to push now?"):
        console.print("[yellow]Skipped.[/yellow] You can push later with:")
        console.print(f"[bold]hw up {repo_name}[/bold]")
        return

    temp_path = Path(tempfile.mkdtemp())
    folder = temp_path / repo_name
    folder.mkdir()

    try:
        for source_file in source_files:
            shutil.copy2(source_file, folder / source_file.name)

        submit_folder(
            folder,
            exercise=None,
            session=None,
            course=None,
            visibility=visibility,
            repo_name=repo_name,
            include_support_files=False,
        )
    except SubmissionSkipped as error:
        print(error)
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


def copy_file_to_temp_folder(source_file, repo_name):
    temp_path = Path(tempfile.mkdtemp())
    repo_folder = temp_path / repo_name
    repo_folder.mkdir()
    shutil.copy2(source_file, repo_folder / source_file.name)
    return temp_path, repo_folder


def submit_single_file(source_file, exercise, session, course, visibility, repo_name=None):
    source_file = Path(source_file)

    if not source_file.exists():
        console.print(f"[red]File not found:[/red] {source_file}")
        return None

    if not source_file.is_file():
        console.print(f"[red]Not a file:[/red] {source_file}")
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

    try:
        submit_single_file(source_file, exercise, session, course, visibility, repo_name)
    except SubmissionSkipped as error:
        print(error)


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
    try:
        answer = input(f"{question} [Y/N]: ").strip().lower()
    except EOFError:
        return False

    return answer in {"y", "yes"}


def print_session_items(items):
    table = Table(title=f"Found {len(items)} file(s)")
    table.add_column("No", justify="right", style="cyan")
    table.add_column("File", style="bold")
    table.add_column("Repository", style="green")

    for index, item in enumerate(items, start=1):
        table.add_row(str(index), item["file"].name, item["repo_name"])

    console.print(table)


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
        console.print(f"[red]Invalid selection:[/red] {error}")
        return []

    selected = [items[number - 1] for number in numbers]

    console.print()
    console.print("[bold]Selected files:[/bold]")
    for item in selected:
        console.print(f"- {item['file'].name} [dim]->[/dim] [green]{item['repo_name']}[/green]")
    console.print()

    return selected


def session_preview(session, course, visibility):
    items = build_session_items(session, course)

    if not items:
        console.print("[yellow]No homework files found in the current folder.[/yellow]")
        return

    print_session_items(items)

    if ask_yes_no("Do you want to push now?"):
        console.print()
        submit_session(session, course, visibility)
    else:
        console.print("[yellow]Skipped.[/yellow] You can push later with:")
        console.print(f"[bold]hw submit-session {int(session)} {course.upper()}[/bold]")


def print_submission_summary(submitted, failed):
    if submitted:
        table = Table(title="Done. Submitted repositories")
        table.add_column("No", justify="right", style="cyan")
        table.add_column("File", style="bold")
        table.add_column("Repository", style="green")
        table.add_column("Link", style="blue")

        for index, item in enumerate(submitted, start=1):
            table.add_row(str(index), item["file"], item["repo_name"], item["repo_url"])

        console.print(table)

        console.print("[bold]Copy these links:[/bold]")
        console.print()

        for item in submitted:
            console.print(item["repo_url"])

    if failed:
        console.print()
        console.print("[red]Failed files:[/red]")
        for item in failed:
            console.print(f"- {item['file']}: {item['reason']}")


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
    console.print()
    console.print(f"[green]Created {output_path.name}[/green]")


def submit_session(session, course, visibility):
    items = build_session_items(session, course)

    if not items:
        console.print("[yellow]No homework files found in the current folder.[/yellow]")
        return

    items = choose_session_items(items)

    if not items:
        console.print("[yellow]No files submitted.[/yellow]")
        return

    submitted = []
    failed = []

    for item in items:
        source_file = item["file"]
        exercise = item["exercise"]
        repo_name = item["repo_name"]

        console.rule(f"Submitting {source_file.name}")

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
        except SubmissionSkipped as error:
            failed.append({"file": source_file.name, "reason": str(error)})
            console.print(f"[yellow]{error}[/yellow]")
        except subprocess.CalledProcessError as error:
            failed.append({"file": source_file.name, "reason": str(error)})
            console.print(f"[red]Failed to submit {source_file.name}. Continuing...[/red]")

        console.print()

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
        console.print("[yellow]No homework folders found.[/yellow]")
        return

    table = Table(title="Repositories will be created")
    table.add_column("Folder", style="bold")
    table.add_column("Repository", style="green")

    for folder in folders:
        repo_name = create_batch_repo_name(exercise, session, course, folder.name)
        table.add_row(folder.name, repo_name)

    console.print(table)


def batch_submit(exercise, session, course, visibility):
    folders = find_homework_folders(Path.cwd())

    if not folders:
        console.print("[yellow]No homework folders found.[/yellow]")
        return

    console.print(f"[bold]Found {len(folders)} homework folder(s).[/bold]")
    console.print()

    submitted = []
    failed = []

    for folder in folders:
        repo_name = create_batch_repo_name(exercise, session, course, folder.name)
        console.rule(f"Submitting {folder.name}")

        try:
            submit_folder(folder, exercise, session, course, visibility, repo_name)
            submitted.append(repo_name)
        except SubmissionSkipped as error:
            failed.append((repo_name, error))
            console.print(f"[yellow]{error}[/yellow]")
        except subprocess.CalledProcessError as error:
            failed.append((repo_name, error))
            console.print(f"[red]Failed to submit {repo_name}. Continuing...[/red]")

        console.print()

    console.print(Panel(
        f"Submitted: {len(submitted)}\nFailed: {len(failed)}",
        title="Batch submit finished",
        border_style="green" if not failed else "yellow",
    ))

    if failed:
        console.print()
        console.print("[red]Failed repositories:[/red]")
        for repo_name, _ in failed:
            console.print(f"- {repo_name}")


def get_command_output(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return None

    output = result.stdout.strip() or result.stderr.strip()
    return output.splitlines()[0] if output else "OK"


def print_check(label, ok, detail=None):
    status = "[green]OK[/green]" if ok else "[red]MISSING[/red]"
    detail_text = detail or ""
    return label, status, detail_text


def doctor():
    console.print(Panel("Homework Repo Tool doctor", border_style="cyan"))
    table = Table()
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    table.add_row(*print_check("Python", True, sys.version.split()[0]))

    git_path = shutil.which("git")
    git_version = get_command_output(["git", "--version"]) if git_path else None
    table.add_row(*print_check("Git", bool(git_path), git_version or "Install Git first."))

    gh_path = shutil.which("gh")
    gh_version = get_command_output(["gh", "--version"]) if gh_path else None
    table.add_row(
        *print_check("GitHub CLI", bool(gh_path), gh_version or "Install GitHub CLI first.")
    )

    if gh_path:
        auth_result = subprocess.run(
            ["gh", "auth", "status"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        table.add_row(
            *print_check(
                "GitHub login",
                auth_result.returncode == 0,
                "Run: gh auth login" if auth_result.returncode != 0 else None,
            )
        )
    else:
        table.add_row(*print_check("GitHub login", False, "Install GitHub CLI first."))

    pipx_path = shutil.which("pipx")
    pipx_version = get_command_output(["pipx", "--version"]) if pipx_path else None
    table.add_row(*print_check("pipx", bool(pipx_path), pipx_version or "Install pipx first."))
    console.print(table)


def guide():
    guide_text = """
Huong dan nhanh Homework Repo Tool

1. Kiem tra may da san sang chua:
   hw doctor

2. Mo Terminal trong folder bai tap.
   Vi du folder co cac file:
   bai1.py
   bai2.html
   mindmap.drawio

3. Xem truoc repo se tao:
   hw session-preview 5 it205

4. Neu danh sach dung, nhap Y de push luon.
   Neu muon dung lenh push rieng:
   hw submit-session 5 it205

5. Khi submit-session hoi "Submit all files?", nhap:
   Y       de nop tat ca file
   N       de chon tung file
   1,3,5   de chi nop file so 1, 3, 5

6. Nop mot file rieng:
   hw submit-file bai1.py 5 it205

7. Xem lai link da nop:
   hw history

8. Tao repo private:
   hw submit-session 5 it205 --visibility private

9. Nop nguyen folder hien tai voi ten repo tuy chon:
   hw up ten-repo-theo-thay

Ghi chu:
- Mac dinh repo la public.
- Ten repo lay theo ten file, vi du bai1.py -> bai1-ss05-IT205.
- Lenh hw up chi upload cac file trong folder (khong tao README.md / .gitignore).
- Tool tu gan topic: homework, it205, ss05.
- Neu repo da ton tai, tool se hoi truoc khi push de.
    """.strip()
    console.print(Panel(guide_text, title="Huong dan", border_style="cyan"))


def main():
    parser = argparse.ArgumentParser(
        description="Tool nop bai len GitHub nhanh cho hoc sinh/sinh vien"
    )

    subparsers = parser.add_subparsers(dest="command")

    preview_parser = subparsers.add_parser(
        "preview",
        help="Xem ten repo theo format ex01-ss05-IT205",
    )
    preview_parser.add_argument("exercise")
    preview_parser.add_argument("session")
    preview_parser.add_argument("course")

    submit_parser = subparsers.add_parser(
        "submit",
        help="Nop nguyen folder hien tai thanh mot repo",
    )
    submit_parser.add_argument("exercise")
    submit_parser.add_argument("session")
    submit_parser.add_argument("course")
    submit_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    submit_file_parser = subparsers.add_parser(
        "submit-file",
        help="Nop mot file cu the thanh mot repo",
    )
    submit_file_parser.add_argument("file")
    submit_file_parser.add_argument("session")
    submit_file_parser.add_argument("course")
    submit_file_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    submit_session_parser = subparsers.add_parser(
        "submit-session",
        help="Quet folder hien tai va nop cac file bai tap",
    )
    submit_session_parser.add_argument("session")
    submit_session_parser.add_argument("course")
    submit_session_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    session_preview_parser = subparsers.add_parser(
        "session-preview",
        help="Xem truoc danh sach repo va hoi co push luon khong",
    )
    session_preview_parser.add_argument("session")
    session_preview_parser.add_argument("course")
    session_preview_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    batch_preview_parser = subparsers.add_parser(
        "batch-preview",
        help="Xem truoc kieu nop moi folder con thanh mot repo",
    )
    batch_preview_parser.add_argument("exercise")
    batch_preview_parser.add_argument("session")
    batch_preview_parser.add_argument("course")

    batch_submit_parser = subparsers.add_parser(
        "batch-submit",
        help="Nop moi folder con thanh mot repo",
    )
    batch_submit_parser.add_argument("exercise")
    batch_submit_parser.add_argument("session")
    batch_submit_parser.add_argument("course")
    batch_submit_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    up_parser = subparsers.add_parser(
        "up",
        help="Nop folder hien tai len GitHub voi ten repo tuy chon",
    )
    up_parser.add_argument(
        "repo_name",
        help="Ten repo dung y chang ten ban nhap (khong tu dong doi).",
    )
    up_parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
    )

    subparsers.add_parser("history", help="Xem lai cac link da nop")
    subparsers.add_parser("doctor", help="Kiem tra Git, GitHub CLI, login, pipx")
    subparsers.add_parser("guide", help="Huong dan su dung bang tieng Viet")

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
    elif args.command == "up":
        up(args.repo_name, args.visibility)
    elif args.command == "history":
        show_history()
    elif args.command == "doctor":
        doctor()
    elif args.command == "guide":
        guide()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
