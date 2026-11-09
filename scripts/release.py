"""Releases: group decided issues in a milestone, then publish a font version.

    python scripts/release.py milestone 1.001   # create milestone "Versie 1.001" on GitHub
    make release V=1.001                        # local: check, bump, rebuild, test, archive, commit + tag
    make publish V=1.001                        # push main + tag, GitHub Release with the TTF, close milestone

`make release` runs, in order:
    release.py check 1.001     clean working tree on main, version higher than the latest release
    release.py bump 1.001      VERSION in scripts/config.py
    make sources build test web-data
    release.py prepare 1.001   copy font + data to web/public/versions/v1.001/, changed characters
                               (scripts/fontdiff.py), notes from the milestone's closed issues,
                               web/public/data/releases.json, commit "Versie 1.001", tag v1.001
Nothing leaves the machine until `make publish`.
"""
import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import export_web  # noqa: E402
from fontdiff import changed  # noqa: E402

REPO = export_web.REPO
PUBLIC = ROOT / "web" / "public"
RELEASES = PUBLIC / "data" / "releases.json"
CONFIG = ROOT / "scripts" / "config.py"
FONT = ROOT / "fonts" / "ttf" / "Cogncur-Regular.ttf"


def run(*cmd, capture=True):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=capture, text=True)
    if r.returncode:
        sys.exit(f"{' '.join(cmd)} failed:\n{r.stderr or r.stdout}")
    return (r.stdout or "").strip()


def parse(version):
    m = re.fullmatch(r"(\d+)\.(\d{3})", version)
    if not m:
        sys.exit(f"version must look like 1.001, not {version!r}")
    return int(m[1]), int(m[2])


def vkey(version):
    major, minor = parse(version)
    return major, minor


def releases():
    return json.loads(RELEASES.read_text()) if RELEASES.exists() else []


def milestone_title(version):
    return f"Versie {version}"


def find_milestone(version):
    out = run("gh", "api", f"repos/{REPO}/milestones?state=all&per_page=100")
    return next((m for m in json.loads(out) if m["title"] == milestone_title(version)), None)


# ---------- commands
def cmd_milestone(version):
    parse(version)
    if find_milestone(version):
        print(f"milestone '{milestone_title(version)}' exists")
        return
    run("gh", "api", f"repos/{REPO}/milestones", "-f", f"title={milestone_title(version)}",
        "-f", "description=Wat in deze versie van het lettertype komt.")
    print(f"created milestone '{milestone_title(version)}': add the decided issues to it on GitHub")


def cmd_check(version, allow_branch=False):
    parse(version)
    if run("git", "status", "--porcelain"):
        sys.exit("the working tree is not clean: commit or stash first")
    branch = run("git", "branch", "--show-current")
    if branch != "main" and not allow_branch:
        sys.exit(f"releases are made from main (now on {branch!r})")
    if run("git", "tag", "--list", f"v{version}"):
        sys.exit(f"tag v{version} exists already")
    last = max((r["version"] for r in releases()), key=vkey, default=None)
    if last and vkey(version) <= vkey(last):
        sys.exit(f"{version} is not higher than the latest release {last}")
    print(f"ok: {version} after {last or '(no release yet)'}, on {branch}")


def cmd_bump(version):
    major, minor = parse(version)
    text = CONFIG.read_text()
    new, n = re.subn(r"^VERSION = \(\d+, \d+\)$", f"VERSION = ({major}, {minor})", text, flags=re.M)
    if n != 1:
        sys.exit("VERSION line not found in scripts/config.py")
    CONFIG.write_text(new)
    print(f"scripts/config.py: VERSION = ({major}, {minor})")


def notes_from_milestone(version):
    """Closed issues in the milestone (number + title), or [] if there is none / gh is unavailable."""
    try:
        m = find_milestone(version)
    except SystemExit as e:
        print(f"  (no notes: {e})")
        return [], None
    if not m:
        print(f"  (no milestone '{milestone_title(version)}': the release has no notes)")
        return [], None
    out = run("gh", "issue", "list", "-R", REPO, "--milestone", m["title"], "--state", "closed",
              "--limit", "200", "--json", "number,title")
    return sorted(json.loads(out), key=lambda i: i["number"]), m["title"]


def cmd_prepare(version, tag=True):
    parse(version)
    built = f"{TTFont(FONT)['head'].fontRevision:.3f}"
    if built != version:
        sys.exit(f"fonts/ttf has version {built}, expected {version}: run `make release V={version}`")
    slug = f"v{version}"
    dest = PUBLIC / "versions" / slug
    if dest.exists():
        sys.exit(f"{dest.relative_to(ROOT)} exists already")
    rel = releases()
    prev = max(rel, key=lambda r: vkey(r["version"]), default=None)

    # the frozen copy the website shows for this version
    (dest / "fonts").mkdir(parents=True)
    (dest / "data").mkdir()
    shutil.copyfile(PUBLIC / "fonts" / "Cogncur-Regular.ttf", dest / "fonts" / "Cogncur-Regular.ttf")
    for name in ("tekens.json", "composites.json", "routes.json", "build.json"):
        if (PUBLIC / "data" / name).exists():
            shutil.copyfile(PUBLIC / "data" / name, dest / "data" / name)

    # this version's stamp ("Versie 1.001 · v1.001 · date" in feedback issues) is its tag
    build = json.loads((dest / "data" / "build.json").read_text())
    build["commit"] = slug
    (dest / "data" / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=1))

    diff = changed(PUBLIC / "versions" / prev["slug"] / "fonts" / "Cogncur-Regular.ttf", FONT) if prev else []
    notes, milestone = notes_from_milestone(version)
    rel.append({"version": version, "slug": slug, "date": datetime.date.today().isoformat(), "tag": slug,
                "milestone": milestone, "notes": notes, "changed": diff, "previous": prev["version"] if prev else None})
    RELEASES.write_text(json.dumps(sorted(rel, key=lambda r: vkey(r["version"])), ensure_ascii=False, indent=1) + "\n")
    export_web.main()   # "in ontwikkeling" now compares with this release
    print(f"{slug}: {len(diff)} characters changed since {prev['version'] if prev else '-'}, {len(notes)} issues in the notes")

    if tag:
        run("git", "add", "scripts/config.py", "web/public")
        run("git", "commit", "-q", "-m", f"Versie {version}\n\n" + "".join(f"- #{n['number']} {n['title']}\n" for n in notes))
        run("git", "tag", "-a", slug, "-m", f"Versie {version}")
        print(f"committed and tagged {slug} (local). Publish with: make publish V={version}")


def release_notes(entry):
    lines = [f"Versie {entry['version']} van het lettertype.", ""]
    if entry["notes"]:
        lines += ["Wat er beslist en verbeterd is:", ""] + [f"- #{n['number']} {n['title']}" for n in entry["notes"]] + [""]
    if entry["previous"]:
        lines.append(f"{len(entry['changed'])} tekens veranderd sinds versie {entry['previous']}.")
    lines += ["", f"Bekijk deze versie: {export_web.SITE_URL}{'versies/'}"]
    return "\n".join(lines)


def cmd_publish(version):
    slug = f"v{version}"
    entry = next((r for r in releases() if r["version"] == version), None)
    if not entry or not run("git", "tag", "--list", slug):
        sys.exit(f"no prepared release {version}: run `make release V={version}` first")
    run("git", "push", "origin", "main", capture=False)
    run("git", "push", "origin", slug, capture=False)
    font = PUBLIC / "versions" / slug / "fonts" / "Cogncur-Regular.ttf"
    asset = ROOT / "build" / f"Cogncur-Regular-{version}.ttf"
    asset.parent.mkdir(exist_ok=True)
    shutil.copyfile(font, asset)
    run("gh", "release", "create", slug, str(asset), "-R", REPO, "--title", f"Versie {version}", "--notes", release_notes(entry))
    m = find_milestone(version)
    if m and m["state"] == "open":
        run("gh", "api", "-X", "PATCH", f"repos/{REPO}/milestones/{m['number']}", "-f", "state=closed")
    print(f"published {slug}: https://github.com/{REPO}/releases/tag/{slug}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["milestone", "check", "bump", "prepare", "publish"])
    ap.add_argument("version")
    ap.add_argument("--allow-branch", action="store_true", help="check: allow a branch other than main (testing)")
    ap.add_argument("--no-tag", action="store_true", help="prepare: don't commit or tag (testing)")
    a = ap.parse_args()
    if a.command == "milestone":
        cmd_milestone(a.version)
    elif a.command == "check":
        cmd_check(a.version, a.allow_branch)
    elif a.command == "bump":
        cmd_bump(a.version)
    elif a.command == "prepare":
        cmd_prepare(a.version, tag=not a.no_tag)
    else:
        cmd_publish(a.version)


if __name__ == "__main__":
    main()
