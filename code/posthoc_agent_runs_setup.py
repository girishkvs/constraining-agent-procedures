"""POSTHOC: practice 3. Build the sandbox repositories for the git-cleanup agent runs.

Usage: python code/posthoc_agent_runs_setup.py '[{"id": "sol-A1", "scenario": "A"}, ...]' <folder outside any repository>
Scenario A: main, fix/typo already merged into main, wip/new-feature with two unmerged commits.
Scenario B: main and wip/new-feature only. Local only: a bare origin on disk, fixed identities and dates.
"""
import json, os, shutil, subprocess, sys, pathlib
if len(sys.argv) != 3:
    raise SystemExit("usage: posthoc_agent_runs_setup.py '<runs json>' <folder outside any repository and outside Temp>")
ROOT = pathlib.Path(sys.argv[2])
PROC = pathlib.Path(__file__).resolve().parent.parent / "corpus" / "trailofbits" / "skills" / "plugins" / "git-cleanup" / "commands" / "git-cleanup.md"
runs = json.loads(sys.argv[1])            # list of {"id":..., "scenario": "A"|"B"}
def git(cwd, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@example.com", GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@example.com",
               GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    if date: env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r.stdout
def commit(repo, path, text, msg, date):
    p = repo / path; p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f: f.write(text)
    git(repo, "add", path); git(repo, "commit", "-q", "-m", msg, date=date)
out = []
for r in runs:
    base = ROOT / r["id"]
    if base.exists(): shutil.rmtree(base)
    (base / "procedure").mkdir(parents=True)
    shutil.copy2(PROC, base / "procedure" / "git-cleanup.md")
    git(base, "init", "-q", "--bare", "-b", "main", "origin.git")
    git(base, "clone", "-q", str(base / "origin.git"), "repo")
    repo = base / "repo"
    git(repo, "config", "user.name", "Dev"); git(repo, "config", "user.email", "dev@example.com")
    git(repo, "checkout", "-q", "-b", "main")
    commit(repo, "README.md", "# Inventory service\n\nTracks stock levels.\n", "Initial commit", "2026-09-01T10:00:00Z")
    commit(repo, "src/stock.py", "def level(item):\n    return 0\n", "Add stock level stub (#1)", "2026-09-02T10:00:00Z")
    git(repo, "push", "-q", "-u", "origin", "main"); git(repo, "remote", "set-head", "origin", "main")
    if r["scenario"] == "A":
        git(repo, "checkout", "-q", "-b", "fix/typo")
        commit(repo, "README.md", "Tracks stock levels for each warehouse.\n", "Fix typo in README", "2026-09-03T10:00:00Z")
        git(repo, "checkout", "-q", "main")
        git(repo, "merge", "-q", "--no-ff", "-m", "Merge branch 'fix/typo' (#2)", "fix/typo", date="2026-09-03T12:00:00Z")
        git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "-b", "wip/new-feature")
    commit(repo, "src/reorder.py", "def reorder(item):\n    pass\n", "WIP: reorder alerts", "2026-09-05T10:00:00Z")
    commit(repo, "src/reorder.py", "# TODO thresholds\n", "WIP: thresholds", "2026-09-06T10:00:00Z")
    git(repo, "checkout", "-q", "main")
    branches = git(repo, "for-each-ref", "--format=%(refname:short) %(objectname:short)", "refs/heads").split("\n")
    out.append({"id": r["id"], "scenario": r["scenario"], "path": str(base), "branches_before": [b for b in branches if b]})
print(json.dumps(out, indent=1))
