import tempfile
import unittest
from pathlib import Path

from docs_output import validate_site
from sync_docs import sync


class DocsOutputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.site = Path(self.directory.name)
        self.base = "https://example.test/project/docs/"
        self.write_page("index.html", self.base, "Introduction | Project", '<a href="guide#section">Guide</a>')
        self.write_page("guide/index.html", self.base + "guide", "Guide | Project", '<h2 id="section">Section</h2>')
        self.urls = [self.base, self.base + "guide"]
        self.write_sitemap()

    def write_page(self, filename, canonical, title, content=""):
        path = self.site / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'<html><head><title>{title}</title><link rel="canonical" href="{canonical}"></head><body>{content}</body></html>', encoding="utf-8")

    def write_sitemap(self):
        content = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        content += "".join(f"<url><loc>{url}</loc></url>" for url in self.urls)
        (self.site / "sitemap.xml").write_text(content + "</urlset>", encoding="utf-8")

    def test_generates_complete_index_and_validates_it_without_rewriting(self):
        self.assertEqual(validate_site(self.site, True), [])
        text = (self.site / "llms.txt").read_text()
        self.assertIn("# Project\n", text)
        self.assertIn(f"- [Guide]({self.base}guide)", text)
        self.assertEqual(validate_site(self.site), [])

    def test_missing_fragment_fails_even_when_html_build_succeeds(self):
        self.write_page("index.html", self.base, "Introduction | Project", '<a href="guide#missing">Guide</a>')
        self.assertTrue(any("Missing fragment" in e for e in validate_site(self.site, True)))

    def test_missing_page_fails(self):
        self.urls.append(self.base + "missing")
        self.write_sitemap()
        self.assertTrue(any("Missing built page" in e for e in validate_site(self.site, True)))

    def test_empty_urls_in_existing_index_fail(self):
        (self.site / "llms.txt").write_text("# Project\n\n- [Introduction]()\n- [Guide]()\n")
        self.assertTrue(any("every sitemap page" in e for e in validate_site(self.site)))

    def test_undefined_title_in_existing_index_fails(self):
        self.assertEqual(validate_site(self.site, True), [])
        path = self.site / "llms.txt"
        path.write_text(path.read_text().replace("# Project", "# undefined", 1))
        self.assertTrue(any("title does not match" in e for e in validate_site(self.site)))

    def test_other_sites_are_ignored_but_internal_missing_links_fail(self):
        self.write_page("index.html", self.base, "Introduction | Project", '<a href="/another/docs/missing">Other project</a><a href="mailto:a@example.test">Email</a>')
        self.assertEqual(validate_site(self.site, True), [])
        self.write_page("index.html", self.base, "Introduction | Project", '<a href="missing">Missing</a>')
        self.assertTrue(any("Missing built page" in e for e in validate_site(self.site, True)))

    def test_duplicate_sitemap_urls_fail(self):
        self.urls.append(self.base)
        self.write_sitemap()
        self.assertTrue(any("duplicate" in e for e in validate_site(self.site, True)))

    def test_wrong_canonical_url_fails(self):
        self.write_page("guide/index.html", self.base + "elsewhere", "Guide | Project")
        self.assertTrue(any("Canonical URL disagrees" in e for e in validate_site(self.site, True)))

    def test_encoded_fragments_are_checked_against_decoded_html_ids(self):
        self.write_page("index.html", self.base, "Introduction | Project", '<a href="guide#caf%C3%A9">Guide</a>')
        self.write_page("guide/index.html", self.base + "guide", "Guide | Project", '<h2 id="café">Section</h2>')
        self.assertEqual(validate_site(self.site, True), [])

    def test_sitemap_cannot_escape_build_directory(self):
        self.urls.append(self.base + "%2e%2e/secrets")
        self.write_sitemap()
        self.assertTrue(any("Unsafe route" in e for e in validate_site(self.site, True)))


class DocsSyncTests(unittest.TestCase):
    def test_rollout_is_idempotent_and_preserves_other_jobs_and_content(self):
        import json

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            docs = repo / "docs"
            docs.mkdir()
            package = {"dependencies": {"@docusaurus/core": "^3.10.2", "docusaurus-plugin-llms-txt": "^0.1.3"}, "scripts": {"build": "docusaurus build", "build:cloudflare": "docusaurus build --out-dir build/project/docs"}}
            (docs / "package.json").write_text(json.dumps(package))
            (docs / "docusaurus.config.ts").write_text("const config = {\n  title: 'Project',\n  plugins: ['docusaurus-plugin-llms-txt'],\n};\n")
            workflows = repo / ".github/workflows"
            workflows.mkdir(parents=True)
            ci = workflows / "ci.yml"
            ci.write_text("jobs:\n  docs:\n    steps:\n      - run: bun run build\n  # Keep the unrelated test job.\n  test:\n    runs-on: ubuntu-latest\n")
            ref = "a" * 40
            sync(repo, ref)
            first = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
            sync(repo, ref)
            second = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
            self.assertEqual(first, second)
            self.assertIn("# Keep the unrelated test job.", ci.read_text())
            self.assertIn("  test:\n    runs-on: ubuntu-latest", ci.read_text())
            self.assertIn("docs.yml@" + ref, ci.read_text())
            self.assertEqual(ci.read_text().count("  docs-validation:"), 1)
            self.assertIn("    name: Docs (Docusaurus)\n    needs: docs-validation", ci.read_text())
            self.assertIn('test "$DOCS_RESULT" = success', ci.read_text())
            self.assertIn("title: 'Project'", (docs / "docusaurus.config.ts").read_text())
            self.assertNotIn("docusaurus-plugin-llms-txt", (docs / "package.json").read_text())


if __name__ == "__main__":
    unittest.main()
