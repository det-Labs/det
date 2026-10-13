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


def sync_wiki(repo_url: str = "https://github.com/det-Labs/det.wiki.git") -> bool:
    wiki_dir = Path(__file__).parent.parent / "wiki"
    if not wiki_dir.is_dir():
        print(f"Error: {wiki_dir} does not exist.")
        return False

    temp_clone = Path(tempfile.mkdtemp())
    print(f"Attempting to clone GitHub Wiki from {repo_url}...")
    clone_res = subprocess.run(["git", "clone", repo_url, str(temp_clone)], capture_output=True, text=True)

    if clone_res.returncode != 0:
        print("\nNote: GitHub Wiki repository could not be cloned.")
        print("Reason: On GitHub, the wiki Git repository is created only AFTER the first page is created in the web UI.")
        print("To initialize the wiki:")
        print("  1. Visit https://github.com/det-Labs/det/wiki")
        print("  2. Click 'Create the first page' and save it (you can paste content from wiki/Home.md).")
        print("  3. Run this script again: python scripts/sync_wiki.py\n")
        return False

    # Copy all markdown files from wiki/ into temp_clone
    print("Copying documentation pages to wiki clone...")
    for f in wiki_dir.glob("*.md"):
        shutil.copy2(f, temp_clone / f.name)

    # Commit and push
    subprocess.run(["git", "add", "."], cwd=temp_clone)
    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=temp_clone, capture_output=True, text=True)
    if not status_res.stdout.strip():
        print("GitHub Wiki is already up to date.")
        return True

    subprocess.run(["git", "commit", "-m", "docs: sync wiki pages from repository"], cwd=temp_clone)
    push_res = subprocess.run(["git", "push", "origin", "master"], cwd=temp_clone, capture_output=True, text=True)
    if push_res.returncode != 0:
        # Try pushing to main
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=temp_clone, capture_output=True, text=True)

    if push_res.returncode == 0:
        print("Successfully synchronized GitHub Wiki pages!")
        return True
    else:
        print(f"Failed to push to GitHub Wiki: {push_res.stderr}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync wiki directory to GitHub Wiki")
    parser.add_argument("--remote", default="https://github.com/det-Labs/det.wiki.git", help="Wiki git URL")
    args = parser.parse_args()
    success = sync_wiki(args.remote)
    sys.exit(0 if success else 1)
