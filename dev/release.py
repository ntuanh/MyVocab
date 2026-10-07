"""Publish a new version of MyVocab. Every installed copy then shows a small
Update button within about half an hour. Run it on the developer's computer,
after committing:

    python3 dev/release.py                  # the next version: v1.2 -> v1.3
    python3 dev/release.py 2.0              # a version of your choice
    python3 dev/release.py --notes "..."    # your own "What's new" instead of the commit list
    python3 dev/release.py --skip-tests     # publish without running tests/run_all.py first

It runs the tests first (tests/run_all.py, about 5 minutes) and stops if any
fail. Then it pushes main to GitHub and makes a GitHub release with MyVocab-Setup.bat
attached (the README's download link points to the newest release). Its notes
list the commits since the last release, so users see what changed. Needs the
GitHub CLI (gh), logged in.
"""
import argparse
import re
import shutil
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def last_release():
    result = subprocess.run(["gh", "release", "view", "--json", "tagName", "-q", ".tagName"],
                            cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def next_version(last):
    numbers = [int(n) for n in re.findall(r"\d+", last or "")] or [1, 0]
    numbers = (numbers + [0])[:2]
    return f"v{numbers[0]}.{numbers[1] + 1}" if last else "v1.0"


def notes_since(last):
    """One line per commit since the last release, without the "feat:" labels."""
    span = f"{last}..HEAD" if last else "HEAD"
    lines = []
    for subject in git("log", "--no-merges", "--pretty=%s", span).splitlines():
        text = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", subject).strip()
        if text and not text.lower().startswith(("docs", "chore", "test")):
            lines.append("- " + text[0].upper() + text[1:])
    return "\n".join(lines) or "- Small fixes and improvements"


def main():
    parser = argparse.ArgumentParser(description="Publish a new MyVocab version.")
    parser.add_argument("version", nargs="?", help="for example 1.3 (default: the next one)")
    parser.add_argument("--notes", help="what's new, in your own words")
    parser.add_argument("--yes", action="store_true", help="do not ask before publishing")
    parser.add_argument("--skip-tests", action="store_true", help="publish without running the tests")
    args = parser.parse_args()

    if not shutil.which("gh"):
        sys.exit("The GitHub CLI (gh) is needed: https://cli.github.com, then: gh auth login")
    if git("branch", "--show-current") != "main":
        sys.exit("Switch to the main branch first: users get main.")
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("Commit your changes first (git status shows what is not committed).")

    git("fetch", "--tags", "origin")
    last = last_release()
    tag = ("v" + args.version.lstrip("v")) if args.version else next_version(last)
    if git("tag", "--list", tag):
        sys.exit(f"{tag} already exists. Choose another version.")
    notes = args.notes or notes_since(last)

    print(f"Last version: {last or 'none'}")
    print(f"New version:  {tag}\n\nWhat's new:\n{notes}\n")
    if not args.skip_tests:
        python = os.path.join(ROOT, ".venv", "Scripts" if os.name == "nt" else "bin", "python")
        print("Running the tests first (tests/run_all.py) ...")
        if subprocess.run([python, os.path.join(ROOT, "tests", "run_all.py")], cwd=ROOT).returncode != 0:
            sys.exit("Some tests failed, so nothing was published. Fix them, or use --skip-tests.")
    if not args.yes and input("Publish it? Every installed MyVocab will offer this update. [y/N] ").strip().lower() != "y":
        sys.exit("Nothing was published.")

    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    subprocess.run(["gh", "release", "create", tag, os.path.join(ROOT, "MyVocab-Setup.bat"),
                    "--target", git("rev-parse", "HEAD"), "--title", f"MyVocab {tag}", "--notes", notes],
                   cwd=ROOT, check=True)
    print(f"\nPublished {tag}. Installed copies show the Update button within about half an hour.")


if __name__ == "__main__":
    main()
