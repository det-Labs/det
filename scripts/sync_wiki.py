"""Synchronize the local wiki/ directory with the GitHub Wiki repository.

Usage:
    python scripts/sync_wiki.py [--remote <wiki_git_url>]
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def _clone_wiki(repo_url: str, target_dir: Path) -> bool:
    """Clone the remote wiki repository into target directory."""
    print(f"Attempting to clone GitHub Wiki from {repo_url}...")
    clone_res = subprocess.run(
        ["git", "clone", repo_url, str(target_dir)],
        capture_output=True,
        text=True,
    )
    if clone_res.returncode != 0:
        print("\nNote: GitHub Wiki repository could not be cloned.")
        print("Reason: On GitHub, the wiki Git repo is created after the first page is created in the web UI.")
        print("To initialize:")
        print("  1. Visit https://github.com/det-Labs/det/wiki")
        print("  2. Click 'Create the first page' and save it.")
        print("  3. Run this script again: python scripts/sync_wiki.py\n")
        return False
    return True


def _copy_and_push(wiki_dir: Path, clone_dir: Path) -> bool:
    """Copy markdown pages to clone and push updates to remote."""
    print("Copying documentation pages to wiki clone...")
    for f in wiki_dir.glob("*.md"):
        shutil.copy2(f, clone_dir / f.name)

    subprocess.run(["git", "add", "."], cwd=clone_dir)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=clone_dir, capture_output=True, text=True)
    if not status.stdout.strip():
        print("GitHub Wiki is already up to date.")
        return True

    subprocess.run(["git", "commit", "-m", "docs: sync wiki pages from repository"], cwd=clone_dir)
    push_res = subprocess.run(["git", "push", "origin", "master"], cwd=clone_dir, capture_output=True, text=True)
    if push_res.returncode != 0:
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=clone_dir, capture_output=True, text=True)

    if push_res.returncode == 0:
        print("Successfully synchronized GitHub Wiki pages!")
        return True
    print(f"Failed to push to GitHub Wiki: {push_res.stderr}")
    return False


def sync_wiki(repo_url: str = "https://github.com/det-Labs/det.wiki.git") -> bool:
    """Synchronize wiki documentation directory with GitHub Wiki."""
    wiki_dir = Path(__file__).resolve().parent.parent / "wiki"
    if not wiki_dir.is_dir():
        print(f"Error: {wiki_dir} does not exist.")
        return False

    temp_clone = Path(tempfile.mkdtemp())
    if not _clone_wiki(repo_url, temp_clone):
        return False
    return _copy_and_push(wiki_dir, temp_clone)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync wiki directory to GitHub Wiki")
    parser.add_argument("--remote", default="https://github.com/det-Labs/det.wiki.git", help="Wiki git URL")
    args = parser.parse_args()
    success = sync_wiki(args.remote)
    sys.exit(0 if success else 1)

