#!/usr/bin/env python3
"""Read-only GitHub org inventory and a persistent local work queue.

Uses authenticated gh, Python's standard library, and no GitHub mutations.
"""

from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / ".work"
SCHEMA_VERSION = 1
BOT_BRANCH = re.compile(r"^(dependabot|renovate|gh-readonly-queue)/", re.I)
SECURITY_TITLE = re.compile(
    r"security|RUSTSEC-|GHSA-|CVE-|arbitrary .*file|capability token.*falls back", re.I
)
REFERENCE = re.compile(
    r"\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?|refs?)\s+"
    r"(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<number>\d+)", re.I
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def gh_json(*args: str, attempts: int = 3):
    """Retry transient reads; never retry authentication or schema errors."""
    for attempt in range(attempts):
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=180
        )
        if result.returncode == 0:
            value = json.loads(result.stdout)
            if isinstance(value, dict) and value.get("errors"):
                raise RuntimeError(json.dumps(value["errors"]))
            return value
        message = result.stderr.strip() or result.stdout.strip()
        transient = re.search(r"HTTP (502|503|504)|connection|timed out", message, re.I)
        if not transient or attempt + 1 == attempts:
            raise RuntimeError(message)
        time.sleep(attempt + 1)
    raise RuntimeError("GitHub read failed")


def private_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value)
    temp.chmod(0o600)
    temp.replace(path)
    path.chmod(0o600)


def write_json(path: Path, value) -> None:
    private_write(path, json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


COMMON = """
    number title url body createdAt updatedAt author { login __typename }
    assignees(first: 30) { nodes { login } }
    labels(first: 30) { nodes { name } }
    comments(last: 10) {
      totalCount pageInfo { hasPreviousPage }
      nodes { body createdAt author { login __typename } }
    }
"""
PR_FIELDS = COMMON + """
    isDraft headRefName headRefOid headRepository { nameWithOwner } isCrossRepository
    baseRefName mergeable mergeStateStatus reviewDecision
    additions deletions changedFiles
    closingIssuesReferences(first: 30) { nodes { number url } }
    reviews(last: 10) {
      totalCount pageInfo { hasPreviousPage }
      nodes { state body submittedAt author { login __typename } }
    }
    commits(last: 1) { nodes { commit { oid statusCheckRollup {
      state contexts(first: 100) {
        totalCount pageInfo { hasNextPage }
        nodes {
          __typename
          ... on CheckRun { name status conclusion detailsUrl startedAt completedAt }
          ... on StatusContext { context state targetUrl createdAt }
        }
      }
    } } } }
"""


def connection_query(field: str, cursor: str | None, fields: str) -> str:
    after = ", after: " + json.dumps(cursor) if cursor else ""
    return (
        f"{field}(first: 30{after}, states: OPEN) {{ totalCount "
        f"pageInfo {{ hasNextPage endCursor }} nodes {{ {fields} }} }}"
    )


def fetch_repository(repo: dict) -> dict:
    owner, name = repo["full_name"].split("/", 1)
    collected = {"issues": [], "pullRequests": [], "branches": []}
    cursors = {"issues": None, "pullRequests": None, "refs": None}
    pending = set(cursors)
    while pending:
        fields = []
        for field in ("issues", "pullRequests"):
            if field in pending:
                fields.append(connection_query(field, cursors[field], COMMON if field == "issues" else PR_FIELDS))
        if "refs" in pending:
            after = ", after: " + json.dumps(cursors["refs"]) if cursors["refs"] else ""
            fields.append(
                'refs(refPrefix: "refs/heads/", first: 100' + after + ") { "
                "pageInfo { hasNextPage endCursor } nodes { name target { oid "
                "... on Commit { committedDate messageHeadline } } } }"
            )
        query = (
            "query { repository(owner: " + json.dumps(owner) + ", name: " + json.dumps(name)
            + ") { " + " ".join(fields) + " } }"
        )
        data = gh_json("api", "graphql", "-f", "query=" + query)["data"]["repository"]
        if data is None:
            raise RuntimeError("Repository is no longer accessible")
        for field in list(pending):
            connection = data[field]
            collected["branches" if field == "refs" else field].extend(connection["nodes"])
            page = connection["pageInfo"]
            if page["hasNextPage"]:
                cursor = page["endCursor"]
                if not cursor or cursor == cursors[field]:
                    raise RuntimeError(f"Pagination did not advance for {field}")
                cursors[field] = cursor
            else:
                pending.remove(field)
    return {
        "name": repo["full_name"], "url": repo["html_url"],
        "private": repo["private"], "archived": repo["archived"],
        "default_branch": repo["default_branch"], **collected,
    }


def branch_work(repo: dict, since: datetime, tracked: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Include recent, unrepresented branches so cloud work is not invisible."""
    represented = {
        pr["headRefName"] for pr in repo["pullRequests"]
        if ((pr.get("headRepository") or {}).get("nameWithOwner") == repo["name"]
            or ("headRepository" not in pr and not pr.get("isCrossRepository")))
    }
    work, errors = [], []
    for branch in repo["branches"]:
        name, head = branch["name"], branch["target"]
        date = timestamp(head.get("committedDate"))
        explicitly_tracked = f"{repo['name']}@{name}" in (tracked or set())
        if (name == repo["default_branch"] or name in represented or BOT_BRANCH.search(name)
                or date is None or (date < since and not explicitly_tracked)):
            continue
        try:
            base = quote(repo["default_branch"], safe="")
            target = quote(name, safe="")
            comparison = gh_json("api", f"repos/{repo['name']}/compare/{base}...{target}?per_page=100")
            if not comparison["ahead_by"]:
                continue
            refs = set()
            commits = comparison.get("commits", [])
            for commit in commits:
                for match in REFERENCE.finditer(commit["commit"]["message"]):
                    refs.add(f"{match.group('repo') or repo['name']}#{match.group('number')}")
            work.append({
                "repo": repo["name"], "name": name, "head_oid": head["oid"],
                "updated_at": head["committedDate"], "title": head.get("messageHeadline", name),
                "url": repo["url"] + "/tree/" + quote(name, safe="/"),
                "ahead_by": comparison["ahead_by"], "behind_by": comparison["behind_by"],
                "commit_references": sorted(refs),
                "references_complete": len(commits) >= comparison["total_commits"],
            })
        except (RuntimeError, subprocess.TimeoutExpired, OSError, KeyError) as exc:
            errors.append({"repo": repo["name"], "branch": name, "error": str(exc)})
    return work, errors


def is_bot(author: dict | None) -> bool:
    author = author or {}
    login = author.get("login", "").lower()
    return author.get("__typename") == "Bot" or author.get("is_bot", False) or login.endswith("[bot]") or login.startswith("app/")


def checks(pr: dict, now: datetime, stale_days: int) -> dict:
    commits = pr.get("commits", {}).get("nodes", [])
    commit = commits[-1]["commit"] if commits else {}
    rollup = commit.get("statusCheckRollup")
    if not rollup:
        return {"state": "NONE", "failures": [], "pending": [], "stale": False, "complete": True}
    connection = rollup["contexts"]
    nodes = connection["nodes"]
    failed, pending, old = [], [], []
    undated_success = False
    for check in nodes:
        name = check.get("name", check.get("context", "unnamed"))
        status = check.get("conclusion") or check.get("state") or check.get("status")
        if status in {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}:
            failed.append(name)
        if status in {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"}:
            pending.append(name)
        date = timestamp(check.get("completedAt") or check.get("createdAt"))
        if status == "SUCCESS" and date is None:
            undated_success = True
        if status == "SUCCESS" and date and now - date > timedelta(days=stale_days):
            old.append(name)
    complete = bool(nodes) and not undated_success and not connection.get("pageInfo", {}).get("hasNextPage", False)
    head_matches = not pr.get("headRefOid") or commit.get("oid") == pr["headRefOid"]
    return {
        "state": rollup["state"], "failures": sorted(failed), "pending": sorted(pending),
        "stale": bool(old), "stale_checks": sorted(old), "complete": complete and head_matches,
    }


def inventory_items(snapshot: dict, state: dict, stale_days: int = 7,
                    now: datetime | None = None) -> list[dict]:
    now = now or timestamp(utc_now())
    overrides = state.get("items", {})
    items = []
    links = {}
    for repo in snapshot["repositories"]:
        for pr in repo["pullRequests"]:
            key = f"{repo['name']}#{pr['number']}"
            for issue in pr.get("closingIssuesReferences", {}).get("nodes", []):
                match = re.search(r"github\.com/([^/]+/[^/]+)/issues/", issue["url"])
                issue_repo = match.group(1) if match else repo["name"]
                links.setdefault(f"{issue_repo}#{issue['number']}", []).append(key)
    for branch in snapshot.get("branch_work", []):
        key = f"{branch['repo']}@{branch['name']}"
        for issue in branch["commit_references"]:
            links.setdefault(issue, []).append(key)
    for repo in snapshot["repositories"]:
        for kind, field in (("issue", "issues"), ("pr", "pullRequests")):
            for raw in repo[field]:
                key = f"{repo['name']}#{raw['number']}"
                author = (raw.get("author") or {}).get("login", "unknown")
                labels = [label["name"] for label in raw["labels"]["nodes"]]
                item = {
                    "key": key, "kind": kind, "repo": repo["name"], "number": raw["number"],
                    "title": raw["title"], "url": raw["url"], "author": author,
                    "updated_at": raw["updatedAt"], "labels": labels,
                    "assignees": [a["login"] for a in raw["assignees"]["nodes"]],
                    "work_links": links.get(key, []), "checks": None, "flags": [],
                }
                if SECURITY_TITLE.search(raw["title"]) or any("security" in label.lower() for label in labels):
                    lane, priority = "security", 1
                elif kind == "pr" and not is_bot(raw.get("author")):
                    lane, priority = "human review", 2
                elif kind == "issue" and author != snapshot.get("viewer") and not is_bot(raw.get("author")):
                    lane, priority = "contributor report", 2
                elif kind == "pr":
                    lane, priority = "dependency maintenance", 4
                else:
                    lane, priority = "backlog", 3
                if kind == "pr":
                    check = checks(raw, now, stale_days)
                    item["checks"] = check
                    item["head_oid"] = raw["headRefOid"]
                    item["review_decision"] = raw.get("reviewDecision")
                    item["merge_state"] = raw["mergeStateStatus"]
                    for condition, flag in (
                        (raw["isDraft"], "draft"),
                        (raw["mergeable"] == "CONFLICTING", "conflict"),
                        (check["state"] == "NONE", "no checks"),
                        (check["state"] in {"FAILURE", "ERROR"}, "failing checks"),
                        (bool(check["pending"]), "checks pending"),
                        (check["stale"], "stale passing checks"),
                        (not check["complete"], "incomplete check evidence"),
                        (raw.get("reviewDecision") == "CHANGES_REQUESTED", "changes requested"),
                        (raw["mergeable"] == "UNKNOWN", "mergeability unknown"),
                    ):
                        if condition:
                            item["flags"].append(flag)
                    if repo.get("stale"):
                        item["flags"].append("repository read failed; cached evidence")
                    # Historical green checks are never presented as permission to merge.
                    item["candidate"] = bool(
                        check["state"] == "SUCCESS" and not item["flags"]
                        and raw["mergeStateStatus"] == "CLEAN"
                    )
                item.update(lane=lane, priority=priority, status="untriaged", owner="", note="")
                if kind == "issue" and repo.get("stale"):
                    item["flags"].append("repository read failed; cached evidence")
                override = overrides.get(key, {})
                item.update({k: v for k, v in override.items() if k in {"priority", "status", "owner", "note"}})
                if kind == "pr" and override.get("head_oid") and override["head_oid"] != raw["headRefOid"]:
                    item["flags"].append("head changed since local review")
                    item["candidate"] = False
                items.append(item)
    for branch in snapshot.get("branch_work", []):
        key = f"{branch['repo']}@{branch['name']}"
        item = {
            "key": key, "kind": "branch", "repo": branch["repo"], "title": branch["name"],
            "url": branch["url"], "updated_at": branch["updated_at"], "author": "",
            "lane": "branch work", "priority": 2, "status": "untriaged", "owner": "", "note": "",
            "flags": [f"{branch['ahead_by']} commits ahead", "no open PR"],
            "head_oid": branch["head_oid"], "checks": None,
            "work_links": branch["commit_references"], "assignees": [], "labels": [],
        }
        if not branch["references_complete"]:
            item["flags"].append("partial commit references")
        if branch.get("stale"):
            item["flags"].append("branch read failed; cached evidence")
        override = overrides.get(key, {})
        item.update({k: v for k, v in override.items() if k in {"priority", "status", "owner", "note"}})
        if override.get("head_oid") and override["head_oid"] != branch["head_oid"]:
            item["flags"].append("head changed since local review")
        items.append(item)
    return sorted(items, key=lambda item: (item["priority"], item["lane"], item["repo"], item["key"]))


def changes(previous: dict | None, current: dict) -> dict:
    def entries(snapshot):
        return {item["key"]: item for item in inventory_items(snapshot, {"items": {}})}
    if not previous:
        return {"baseline": True, "new": [], "removed": [], "changed": []}
    old, new = entries(previous), entries(current)
    covered = {repo["name"] for repo in current["repositories"] if not repo.get("stale")}
    # A failed repository read is not a closed issue. Missing org access is not closure either.
    removed = [key for key in old.keys() - new.keys() if old[key]["repo"] in covered and old[key]["kind"] != "branch"]
    updated = []
    for key in old.keys() & new.keys():
        if any(old[key].get(field) != new[key].get(field) for field in (
                "updated_at", "head_oid", "flags", "checks", "work_links")):
            updated.append(key)
    return {"baseline": False, "new": sorted(new.keys() - old.keys()), "removed": sorted(removed), "changed": sorted(updated)}


def fresh_count(snapshot: dict) -> int:
    return sum(not repo.get("stale") for repo in snapshot["repositories"])


def preserve_failed_reads(previous: dict | None, current: dict) -> None:
    """Retain failed reads, including repositories no longer visible in the org."""
    if not previous:
        return
    names = {repo["name"] for repo in current["repositories"]}
    failed = {error["repo"] for error in current["errors"] if "branch" not in error}
    for repo in previous["repositories"]:
        if repo["name"] in failed and repo["name"] not in names:
            cached = copy.deepcopy(repo)
            cached["stale"] = True
            current["repositories"].append(cached)
    present_branches = {(branch["repo"], branch["name"]) for branch in current["branch_work"]}
    failed_branches = {(error["repo"], error["branch"]) for error in current["errors"] if "branch" in error}
    for branch in previous.get("branch_work", []):
        key = (branch["repo"], branch["name"])
        if (branch["repo"] in failed or key in failed_branches) and key not in present_branches:
            cached = copy.deepcopy(branch)
            cached["stale"] = True
            current["branch_work"].append(cached)
    current["repositories"].sort(key=lambda repo: repo["name"].lower())
    current["branch_work"].sort(key=lambda branch: (branch["repo"], branch["name"]))


def markdown_report(snapshot: dict, state: dict, stale_days: int) -> str:
    items = inventory_items(snapshot, state, stale_days)
    issues = sum(len(repo["issues"]) for repo in snapshot["repositories"])
    prs = sum(len(repo["pullRequests"]) for repo in snapshot["repositories"])
    delta = snapshot.get("changes", {})
    lines = [
        "# Sigilweaver work queue", "", f"Snapshot: {snapshot['captured_at']}", "",
        f"Fresh coverage: {fresh_count(snapshot)}/{snapshot['repository_count']} repositories; "
        f"{issues} open issues, {prs} open PRs, {len(snapshot.get('branch_work', []))} recent branches without open PRs.",
        f"Organization listing: {snapshot.get('listed_repository_count', snapshot['repository_count'])} accessible repositories; "
        f"{snapshot['repository_count']} known repositories retained.",
        "", "GitHub data is read-only. Priorities and work status below are local triage, not GitHub labels or review approvals.",
        f"Passing checks older than {stale_days} days are flagged. Passing checks do not establish merge readiness.", "",
    ]
    if snapshot.get("errors"):
        lines += ["## Incomplete reads", ""]
        for error in snapshot["errors"]:
            lines.append(f"- {error.get('repo', 'organization')}: {error['error']}")
        lines.append("")
    if delta.get("baseline"):
        lines += ["Changes: first snapshot establishes the baseline.", ""]
    else:
        lines += [f"Changes: {len(delta.get('new', []))} new, {len(delta.get('changed', []))} updated, "
                  f"{len(delta.get('removed', []))} no longer open.", ""]
        for label, field in (("New", "new"), ("Updated", "changed"), ("No longer open", "removed")):
            if delta.get(field):
                lines += [f"{label}: " + ", ".join(delta[field]), ""]
    for lane in ("security", "human review", "contributor report", "branch work", "backlog", "dependency maintenance"):
        selected = [item for item in items if item["lane"] == lane]
        if not selected:
            continue
        lines += ["## " + lane.title(), "", "| Work | State / owner | Evidence / next action |", "| --- | --- | --- |"]
        for item in selected:
            def escape(value):
                return str(value).replace("|", "\\|").replace("\n", " ")
            evidence = list(item["flags"])
            if item.get("checks"):
                evidence.insert(0, "checks " + item["checks"]["state"])
                if item["checks"]["failures"]:
                    evidence.append("failed: " + ", ".join(item["checks"]["failures"]))
            if item["work_links"]:
                evidence.append("related work: " + ", ".join(item["work_links"]))
            if item["note"]:
                evidence.append(item["note"])
            state_owner = f"P{item['priority']} {item['status']}" + (" / " + item["owner"] if item["owner"] else "")
            lines.append(f"| [{escape(item['key'])}]({item['url']}) {escape(item['title'])} | "
                         f"{escape(state_owner)} | {escape('; '.join(evidence))} |")
        lines.append("")
    lines += ["## Repository coverage", "", "| Repository | Issues | PRs | Visibility |", "| --- | ---: | ---: | --- |"]
    for repo in snapshot["repositories"]:
        lines.append(f"| [{repo['name']}]({repo['url']}) | {len(repo['issues'])} | {len(repo['pullRequests'])} | "
                     f"{'private' if repo['private'] else 'public'} |")
    lines += ["", "Recent discussion context is limited to the last 10 comments/reviews per item. Full item bodies remain in snapshot.json.", ""]
    return "\n".join(lines)


def html_report(snapshot: dict, state: dict, stale_days: int) -> str:
    payload = json.dumps(inventory_items(snapshot, state, stale_days), ensure_ascii=True).replace("<", "\\u003c").replace("&", "\\u0026")
    coverage = f"{fresh_count(snapshot)}/{snapshot['repository_count']} repositories freshly read"
    coverage += f" | {snapshot.get('listed_repository_count', snapshot['repository_count'])} repositories in current org listing"
    warnings = ""
    if snapshot.get("errors"):
        warnings = '<section role="alert"><h2>Incomplete reads</h2><ul>' + "".join(
            "<li>" + html.escape(error.get("repo", "organization") +
            ("@" + error["branch"] if error.get("branch") else "") + ": " + error["error"]) + "</li>"
            for error in snapshot["errors"]
        ) + "</ul><p>Cached items are marked. Missing reads are not closures.</p></section>"
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sigilweaver work queue</title>
<style>body{font:16px system-ui,sans-serif;background:#101820;color:#e7edf2;margin:0;padding:24px}
main{max-width:1200px;margin:auto}h1{margin-bottom:6px}p{color:#a8bac7}input,select{background:#1b2b38;color:inherit;border:1px solid #526575;border-radius:5px;padding:9px;margin:6px 8px 12px 0}
article{background:#1b2b38;border:1px solid #304553;border-radius:7px;padding:16px;margin:10px 0}a{color:#8ecff0}small{color:#b5c6d2}.flags{color:#f3c988}header{display:flex;justify-content:space-between;gap:16px}h2{font-size:18px;margin:8px 0}.note{white-space:pre-wrap}button{padding:8px}#count{margin:12px 0}</style>
<main><h1>Sigilweaver work queue</h1><p>""" + html.escape(snapshot["captured_at"] + " | " + coverage) + """</p>
""" + warnings + """<p>Local triage. Passing checks are evidence, not merge approval. Refresh with the CLI; this page makes no network requests.</p>
<input id="search" aria-label="Search work" placeholder="Search repo, title, owner, notes">
<select id="lane" aria-label="Queue"><option value="">All queues</option></select>
<select id="state" aria-label="Work state"><option value="">All work states</option></select>
<label><input id="hide" type="checkbox">Hide waiting, blocked and done</label><div id="count"></div><div id="items"></div></main>
<script>const data=""" + payload + """;
const el=id=>document.getElementById(id), escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
for(const field of ['lane','state']){const key=field==='state'?'status':field;for(const value of [...new Set(data.map(x=>x[key]))].sort()){const option=document.createElement('option');option.value=value;option.textContent=value;el(field).append(option)}}
function render(){const search=el('search').value.toLowerCase();const items=data.filter(x=>(!el('lane').value||x.lane===el('lane').value)&&(!el('state').value||x.status===el('state').value)&&(!el('hide').checked||!['waiting','blocked','done'].includes(x.status))&&JSON.stringify(x).toLowerCase().includes(search));el('count').textContent=items.length+' of '+data.length+' work items';el('items').innerHTML=items.map(x=>'<article><header><a href="'+escape(x.url)+'" target="_blank" rel="noopener noreferrer">'+escape(x.key)+'</a><small>P'+escape(x.priority)+' | '+escape(x.lane)+' | '+escape(x.status)+(x.owner?' | '+escape(x.owner):'')+'</small></header><h2>'+escape(x.title)+'</h2><div class="flags">'+escape([...(x.checks?['checks '+x.checks.state]:[]),...x.flags].join(' | '))+'</div>'+(x.work_links.length?'<p>Related work: '+escape(x.work_links.join(', '))+'</p>':'')+(x.note?'<p class="note">'+escape(x.note)+'</p>':'')+'</article>').join('')}
for(const id of ['search','lane','state','hide'])el(id).addEventListener('input',render);render();</script></html>"""


def render_reports(directory: Path, snapshot: dict, state: dict, stale_days: int) -> None:
    private_write(directory / "queue.md", markdown_report(snapshot, state, stale_days))
    private_write(directory / "queue.html", html_report(snapshot, state, stale_days))


def sync(args) -> int:
    previous = read_json(args.data_dir / "snapshot.json")
    if previous and previous["org"] != args.org:
        raise RuntimeError("Use a different --data-dir for a different organization")
    state = read_json(args.data_dir / "state.json", {"schema_version": SCHEMA_VERSION, "items": {}})
    tracked = {key for key, value in state["items"].items() if "@" in key and value.get("status") != "done"}
    pages = gh_json("api", f"orgs/{quote(args.org, safe='')}/repos?per_page=100", "--paginate", "--slurp")
    repos = [repo for page in pages for repo in page]
    listed_names = {repo["full_name"] for repo in repos}
    viewer = gh_json("api", "user")["login"]
    results, errors, branches = [], [], []
    since = datetime.now(timezone.utc) - timedelta(days=args.branch_days)
    def fetch(repo):
        result = fetch_repository(repo)
        work, failed = branch_work(result, since, tracked)
        return result, work, failed
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(fetch, repo): repo["full_name"] for repo in repos}
        for future in as_completed(futures):
            name = futures[future]
            try:
                result, work, failed = future.result()
                results.append(result)
                branches.extend(work)
                errors.extend(failed)
                print(f"{name}: {len(result['issues'])} issues, {len(result['pullRequests'])} PRs, {len(work)} branch work items", file=sys.stderr)
            except (RuntimeError, subprocess.TimeoutExpired, OSError, KeyError, ValueError) as exc:
                errors.append({"repo": name, "error": str(exc)})
                print(f"{name}: read failed: {exc}", file=sys.stderr)
    known_names = listed_names | {repo["name"] for repo in (previous or {}).get("repositories", [])}
    for name in sorted(known_names - listed_names):
        errors.append({"repo": name, "error": "Previously visible repository is missing from the organization listing; cached work retained"})
    snapshot = {
        "schema_version": SCHEMA_VERSION, "org": args.org, "viewer": viewer,
        "captured_at": utc_now(), "repository_count": len(known_names), "listed_repository_count": len(repos),
        "repositories": sorted(results, key=lambda repo: repo["name"].lower()),
        "branch_work": sorted(branches, key=lambda work: (work["repo"], work["name"])),
        "branch_window_days": args.branch_days, "errors": errors,
    }
    preserve_failed_reads(previous, snapshot)
    snapshot["changes"] = changes(previous, snapshot)
    if previous:
        write_json(args.data_dir / "previous.json", previous)
    write_json(args.data_dir / "snapshot.json", snapshot)
    if not (args.data_dir / "state.json").exists():
        write_json(args.data_dir / "state.json", state)
    render_reports(args.data_dir, snapshot, state, args.stale_days)
    print(f"Reports: {args.data_dir / 'queue.html'} and {args.data_dir / 'queue.md'}")
    print(f"Coverage: {len(results)}/{len(known_names)} known repositories; {len(repos)} listed, {len(errors)} read errors")
    return 1 if errors else 0


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    cli.add_argument("--stale-days", type=int, default=7)
    sub = cli.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("sync", help="Read all org repositories, issues, PRs and recent branch work")
    fetch.add_argument("--org", default="Sigilweaver")
    fetch.add_argument("--jobs", type=int, default=4)
    fetch.add_argument("--branch-days", type=int, default=14)
    sub.add_parser("report", help="Rebuild reports from the saved snapshot without network access")
    update = sub.add_parser("track", help="Set local work state; does not change GitHub")
    update.add_argument("key", help="owner/repo#number or owner/repo@branch")
    update.add_argument("--status", choices=["untriaged", "ready", "investigating", "in-progress", "waiting", "blocked", "review", "done"])
    update.add_argument("--owner")
    update.add_argument("--priority", type=int, choices=range(1, 6))
    update.add_argument("--note")
    return cli


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.stale_days < 0 or (args.command == "sync" and (args.jobs < 1 or args.branch_days < 0)):
        raise RuntimeError("Days must be nonnegative and jobs must be positive")
    if args.command == "sync":
        return sync(args)
    snapshot = read_json(args.data_dir / "snapshot.json")
    if not snapshot:
        raise RuntimeError("No snapshot. Run sync first.")
    state = read_json(args.data_dir / "state.json", {"schema_version": SCHEMA_VERSION, "items": {}})
    if args.command == "track":
        items = {item["key"]: item for item in inventory_items(snapshot, state, args.stale_days)}
        if args.key not in items:
            raise RuntimeError("Unknown work key: " + args.key)
        updates = {field: getattr(args, field) for field in ("status", "owner", "priority", "note") if getattr(args, field) is not None}
        if not updates:
            raise RuntimeError("Provide a status, owner, priority or note")
        entry = state["items"].setdefault(args.key, {})
        entry.update(updates)
        entry["updated_at"] = utc_now()
        if items[args.key].get("head_oid") and (not entry.get("head_oid") or args.status is not None):
            entry["head_oid"] = items[args.key]["head_oid"]
        write_json(args.data_dir / "state.json", state)
    render_reports(args.data_dir, snapshot, state, args.stale_days)
    print(args.data_dir / "queue.html")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        print(f"org-work: {error}", file=sys.stderr)
        raise SystemExit(2)
