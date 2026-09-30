"""Regression tests for org coverage, evidence freshness and local state."""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import org_work as work


NOW = "2026-09-29T12:00:00Z"


def issue(number=1):
    return {
        "number": number, "title": "Human bug report", "url": f"https://github.com/Sigilweaver/Test/issues/{number}",
        "body": "details", "createdAt": NOW, "updatedAt": NOW,
        "author": {"login": "contributor", "__typename": "User"},
        "labels": {"nodes": []}, "assignees": {"nodes": []},
        "comments": {"totalCount": 0, "nodes": []},
    }


def pull(number=2, date=NOW):
    result = issue(number)
    result.update({
        "title": "chore(deps): patch library", "isDraft": False,
        "author": {"login": "dependabot", "__typename": "Bot"},
        "headRefName": "dependabot/example", "headRefOid": "current-head", "baseRefName": "main",
        "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "reviewDecision": None,
        "closingIssuesReferences": {"nodes": []},
        "commits": {"nodes": [{"commit": {"oid": "current-head", "statusCheckRollup": {
            "state": "SUCCESS", "contexts": {"totalCount": 1, "pageInfo": {"hasNextPage": False},
                "nodes": [{"__typename": "CheckRun", "name": "cargo audit", "status": "COMPLETED",
                           "conclusion": "SUCCESS", "completedAt": date}]},
        }}}]},
    })
    return result


def repository():
    return {
        "name": "Sigilweaver/Test", "url": "https://github.com/Sigilweaver/Test", "private": True,
        "archived": False, "default_branch": "main", "issues": [issue()], "pullRequests": [pull()], "branches": [],
    }


def snapshot():
    return {
        "schema_version": 1, "org": "Sigilweaver", "viewer": "maintainer", "captured_at": NOW,
        "repository_count": 1, "repositories": [repository()], "branch_work": [], "errors": [],
        "changes": {"baseline": True},
    }


class OrgWorkTests(unittest.TestCase):
    def setUp(self):
        clock = patch.object(work, "utc_now", return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)

    def test_html_surfaces_partial_branch_reads(self):
        snap = snapshot()
        snap["errors"] = [{"repo": "Sigilweaver/Test", "branch": "cloud/work", "error": "branch comparison failed"}]
        self.assertIn("branch comparison failed", work.html_report(snap, {}, 7))

    def test_note_only_update_does_not_reapprove_a_changed_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work.write_json(root / "snapshot.json", snapshot())
            state = {"items": {"Sigilweaver/Test#2": {
                "status": "review", "head_oid": "old-head", "note": "Reviewed old commit",
            }}}
            work.write_json(root / "state.json", state)
            with patch.object(work, "gh_json", side_effect=AssertionError("network called")):
                work.main(["--data-dir", directory, "track", "Sigilweaver/Test#2", "--note", "Assign follow-up"])
            saved = work.read_json(root / "state.json")
            self.assertEqual(saved["items"]["Sigilweaver/Test#2"]["head_oid"], "old-head")
            item = next(x for x in work.inventory_items(snapshot(), saved) if x["kind"] == "pr")
            self.assertIn("head changed since local review", item["flags"])
            self.assertFalse(item["candidate"])

    def test_fork_pr_does_not_hide_same_named_local_branch(self):
        repo = repository()
        pr = repo["pullRequests"][0]
        pr.update(headRefName="cloud/work", isCrossRepository=True,
                  headRepository={"nameWithOwner": "contributor/Test"})
        repo["branches"] = [{"name": "cloud/work", "target": {
            "oid": "local-head", "committedDate": NOW, "messageHeadline": "Local work",
        }}]
        comparison = {"ahead_by": 1, "behind_by": 0, "total_commits": 1,
                      "commits": [{"commit": {"message": "Local work"}}]}
        with patch.object(work, "gh_json", return_value=comparison):
            branches, errors = work.branch_work(repo, datetime(2026, 9, 1, tzinfo=timezone.utc))
        self.assertEqual(errors, [])
        self.assertEqual([x["name"] for x in branches], ["cloud/work"])

    def test_report_time_rechecks_evidence_age(self):
        item = next(x for x in work.inventory_items(
            snapshot(), {}, now=datetime(2026, 10, 20, tzinfo=timezone.utc),
        ) if x["kind"] == "pr")
        self.assertIn("stale passing checks", item["flags"])
        self.assertFalse(item["candidate"])

    def test_undated_success_is_incomplete_evidence(self):
        for date in (None, "not-a-timestamp"):
            with self.subTest(date=date):
                snap = snapshot()
                pr = snap["repositories"][0]["pullRequests"][0]
                pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][0]["completedAt"] = date
                item = next(x for x in work.inventory_items(snap, {}) if x["kind"] == "pr")
                self.assertIn("incomplete check evidence", item["flags"])
                self.assertFalse(item["candidate"])

    def test_tracked_branch_retains_work_beyond_recent_window(self):
        repo = repository()
        repo["branches"] = [{"name": "cloud/work", "target": {
            "oid": "cloud-head", "committedDate": "2026-08-01T12:00:00Z", "messageHeadline": "Unfinished work",
        }}]
        comparison = {"ahead_by": 1, "behind_by": 0, "total_commits": 1,
                      "commits": [{"commit": {"message": "Unfinished work"}}]}
        since = datetime(2026, 9, 15, tzinfo=timezone.utc)
        with patch.object(work, "gh_json", return_value=comparison) as gh:
            untracked, errors = work.branch_work(repo, since)
            self.assertEqual(untracked, [])
            gh.assert_not_called()
            tracked, errors = work.branch_work(repo, since, {"Sigilweaver/Test@cloud/work"})
        self.assertEqual(errors, [])
        self.assertEqual([x["name"] for x in tracked], ["cloud/work"])

    def test_lost_org_listing_then_restored_access_preserves_closure_detection(self):
        raw = {"full_name": "Sigilweaver/Test", "html_url": "https://github.com/Sigilweaver/Test",
               "private": True, "archived": False, "default_branch": "main"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work.write_json(root / "snapshot.json", snapshot())
            args = work.parser().parse_args(["--data-dir", directory, "sync"])
            with patch.object(work, "gh_json", side_effect=[[], {"login": "maintainer"}]):
                self.assertEqual(work.sync(args), 1)
            lost = work.read_json(root / "snapshot.json")
            self.assertEqual(len(lost["repositories"]), 1)
            self.assertTrue(lost["repositories"][0]["stale"])
            self.assertEqual(lost["changes"]["removed"], [])
            self.assertTrue(lost["errors"])
            healthy = repository()
            healthy["issues"] = []
            with patch.object(work, "gh_json", side_effect=[[[raw]], {"login": "maintainer"}]), \
                    patch.object(work, "fetch_repository", return_value=healthy):
                self.assertEqual(work.sync(args), 0)
            current = work.read_json(root / "snapshot.json")
            self.assertEqual(current["changes"]["removed"], ["Sigilweaver/Test#1"])

    def test_failed_repo_survives_until_next_successful_closure_read(self):
        raw = {"full_name": "Sigilweaver/Test", "html_url": "https://github.com/Sigilweaver/Test",
               "private": True, "archived": False, "default_branch": "main"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work.write_json(root / "snapshot.json", snapshot())
            args = work.parser().parse_args(["--data-dir", directory, "sync"])
            with patch.object(work, "gh_json", side_effect=[[[raw]], {"login": "maintainer"}]), \
                    patch.object(work, "fetch_repository", side_effect=RuntimeError("403 read failure")):
                self.assertEqual(work.sync(args), 1)
            failed = work.read_json(root / "snapshot.json")
            self.assertEqual(len(failed["repositories"]), 1)
            self.assertTrue(failed["repositories"][0]["stale"])
            pr = next(x for x in work.inventory_items(failed, {}) if x["kind"] == "pr")
            self.assertFalse(pr["candidate"])
            healthy = repository()
            healthy["issues"] = []
            with patch.object(work, "gh_json", side_effect=[[[raw]], {"login": "maintainer"}]), \
                    patch.object(work, "fetch_repository", return_value=healthy):
                self.assertEqual(work.sync(args), 0)
            current = work.read_json(root / "snapshot.json")
            self.assertEqual(current["changes"]["removed"], ["Sigilweaver/Test#1"])

    def test_stale_carried_repository_does_not_establish_closure_or_candidate(self):
        old = snapshot()
        current = snapshot()
        current["repositories"][0].update(stale=True, issues=[])
        self.assertEqual(work.changes(old, current)["removed"], [])
        item = next(x for x in work.inventory_items(current, {}) if x["kind"] == "pr")
        self.assertFalse(item["candidate"])

    def test_another_org_cannot_overwrite_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = snapshot()
            old["org"] = "OtherOrg"
            work.write_json(root / "snapshot.json", old)
            args = work.parser().parse_args(["--data-dir", directory, "sync"])
            with patch.object(work, "gh_json", side_effect=[[], {"login": "maintainer"}]):
                with self.assertRaisesRegex(RuntimeError, "different.*organization"):
                    work.sync(args)
            self.assertEqual(work.read_json(root / "snapshot.json"), old)

    def test_bot_identity_uses_graphql_type_and_cli_identity(self):
        self.assertTrue(work.is_bot({"login": "dependabot", "__typename": "Bot"}))
        self.assertTrue(work.is_bot({"login": "app/dependabot"}))
        self.assertFalse(work.is_bot({"login": "bherila", "is_bot": False}))

    def test_stale_audit_is_not_a_candidate_even_with_newer_other_check(self):
        snap = snapshot()
        pr = pull(date="2026-08-22T12:00:00Z")
        contexts = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
        contexts["nodes"].append({"__typename": "StatusContext", "context": "docs", "state": "SUCCESS", "createdAt": NOW})
        snap["repositories"][0]["pullRequests"] = [pr]
        item = next(x for x in work.inventory_items(snap, {}) if x["kind"] == "pr")
        self.assertIn("stale passing checks", item["flags"])
        self.assertFalse(item["candidate"])

    def test_no_checks_conflicts_and_incomplete_contexts_do_not_pass(self):
        for mode in ("missing", "conflict", "partial", "wrong-head"):
            with self.subTest(mode=mode):
                snap = snapshot()
                pr = snap["repositories"][0]["pullRequests"][0]
                commit = pr["commits"]["nodes"][0]["commit"]
                if mode == "missing":
                    commit["statusCheckRollup"] = None
                elif mode == "conflict":
                    pr.update(mergeable="CONFLICTING", mergeStateStatus="DIRTY")
                elif mode == "partial":
                    commit["statusCheckRollup"]["contexts"]["pageInfo"]["hasNextPage"] = True
                else:
                    commit["oid"] = "old-head"
                item = next(x for x in work.inventory_items(snap, {}) if x["kind"] == "pr")
                self.assertFalse(item["candidate"])

    def test_local_review_survives_sync_but_head_change_is_flagged(self):
        state = {"items": {"Sigilweaver/Test#2": {"owner": "reviewer", "status": "review", "note": "Check ordinals", "head_oid": "old-head"}}}
        item = next(x for x in work.inventory_items(snapshot(), state) if x["kind"] == "pr")
        self.assertEqual(item["owner"], "reviewer")
        self.assertEqual(item["note"], "Check ordinals")
        self.assertIn("head changed since local review", item["flags"])
        self.assertFalse(item["candidate"])

    def test_missing_repo_or_failed_read_is_not_a_closed_issue(self):
        old = snapshot()
        current = snapshot()
        current["repositories"] = []
        current["errors"] = [{"repo": "Sigilweaver/Test", "error": "403"}]
        self.assertEqual(work.changes(old, current)["removed"], [])

    def test_complete_read_detects_no_longer_open_and_new_items(self):
        old = snapshot()
        current = snapshot()
        current["repositories"][0]["issues"] = [issue(3)]
        delta = work.changes(old, current)
        self.assertEqual(delta["new"], ["Sigilweaver/Test#3"])
        self.assertEqual(delta["removed"], ["Sigilweaver/Test#1"])

    def test_repository_connections_are_paginated_independently(self):
        raw = {"full_name": "Sigilweaver/Test", "html_url": "https://github.com/Sigilweaver/Test", "private": True, "archived": False, "default_branch": "main"}
        first = {"data": {"repository": {
            "issues": {"nodes": [issue()], "pageInfo": {"hasNextPage": True, "endCursor": "issue-cursor"}},
            "pullRequests": {"nodes": [pull()], "pageInfo": {"hasNextPage": False, "endCursor": "pr-cursor"}},
            "refs": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}}
        second = {"data": {"repository": {"issues": {"nodes": [issue(3)], "pageInfo": {"hasNextPage": False, "endCursor": "last"}}}}}
        with patch.object(work, "gh_json", side_effect=[first, second]) as gh:
            result = work.fetch_repository(raw)
        self.assertEqual([x["number"] for x in result["issues"]], [1, 3])
        query = gh.call_args_list[1].args[-1]
        self.assertIn('after: "issue-cursor"', query)
        self.assertNotIn("pullRequests(", query)
        self.assertNotIn("refs(", query)

    def test_branch_work_discovery_and_related_issues(self):
        repo = repository()
        repo["branches"] = [
            {"name": "main", "target": {"oid": "main", "committedDate": NOW}},
            {"name": "dependabot/example", "target": {"oid": "dep", "committedDate": NOW}},
            {"name": "claude/cloud", "target": {"oid": "cloud", "committedDate": NOW, "messageHeadline": "Finish work"}},
        ]
        comparison = {"ahead_by": 90, "behind_by": 0, "total_commits": 1, "commits": [{"commit": {"message": "Fix gap\n\nCloses #1\nRefs Sigilweaver/Other#9"}}]}
        with patch.object(work, "gh_json", return_value=comparison) as gh:
            branches, errors = work.branch_work(repo, datetime(2026, 9, 1, tzinfo=timezone.utc))
        self.assertEqual(len(branches), 1)
        self.assertEqual(errors, [])
        self.assertIn("claude%2Fcloud", gh.call_args.args[1])
        self.assertEqual(branches[0]["commit_references"], ["Sigilweaver/Other#9", "Sigilweaver/Test#1"])
        snap = snapshot()
        snap["branch_work"] = branches
        item = next(x for x in work.inventory_items(snap, {}) if x["kind"] == "issue")
        self.assertEqual(item["work_links"], ["Sigilweaver/Test@claude/cloud"])

    def test_cross_repo_closing_reference_is_not_assigned_to_pr_repo(self):
        snap = snapshot()
        snap["repositories"][0]["pullRequests"][0]["closingIssuesReferences"]["nodes"] = [{"number": 1, "url": "https://github.com/Sigilweaver/Other/issues/1"}]
        item = next(x for x in work.inventory_items(snap, {}) if x["kind"] == "issue")
        self.assertEqual(item["work_links"], [])

    def test_html_escapes_script_terminator_and_private_files_stay_private(self):
        snap = snapshot()
        snap["repositories"][0]["issues"][0]["title"] = "</script><script>alert(1)</script>"
        report = work.html_report(snap, {}, 7)
        self.assertNotIn("</script><script>alert", report)
        self.assertIn("\\u003c/script>", report)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            work.write_json(path, snap)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(work.read_json(path), snap)

    def test_track_is_local_and_preserves_existing_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work.write_json(root / "snapshot.json", snapshot())
            with patch.object(work, "gh_json", side_effect=AssertionError("network called")):
                self.assertEqual(work.main(["--data-dir", directory, "track", "Sigilweaver/Test#2", "--owner", "reviewer", "--note", "Review gap accounting"]), 0)
                self.assertEqual(work.main(["--data-dir", directory, "track", "Sigilweaver/Test#2", "--status", "review"]), 0)
            state = work.read_json(root / "state.json")["items"]["Sigilweaver/Test#2"]
            self.assertEqual(state["note"], "Review gap accounting")
            self.assertEqual(state["status"], "review")
            self.assertEqual(state["head_oid"], "current-head")
            self.assertTrue((root / "queue.html").exists())


if __name__ == "__main__":
    unittest.main()
