import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_required_open_source_files_exist(self):
        required = [
            "LICENSE",
            "NOTICE",
            "README.md",
            "README.zh-CN.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "GOVERNANCE.md",
            "CODE_OF_CONDUCT.md",
            "MAINTAINERS.md",
            "THIRD_PARTY_NOTICES.md",
            ".github/CODEOWNERS",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/ISSUE_TEMPLATE/adoption_report.yml",
            "docs/impact.md",
            "docs/security-model.md",
            "docs/architecture.md",
            "docs/CODEX_FOR_OSS_APPLICATION.md",
        ]
        missing = [name for name in required if not (ROOT / name).exists()]
        self.assertEqual(missing, [])

    def test_public_docs_make_oss_and_privacy_commitments(self):
        readme = self.read("README.md")
        zh_readme = self.read("README.zh-CN.md")
        security = self.read("SECURITY.md")
        codeowners = self.read(".github/CODEOWNERS")

        for text in (readme, zh_readme):
            self.assertIn("Apache-2.0", text)
            self.assertIn("GitHub Releases", text)
            self.assertIn("BYOK", text)
            self.assertIn("mili-xi", text)
            self.assertIn("SECURITY.md", text)
            self.assertNotIn("](./dist/", text)
            self.assertNotIn("app-resources/.env", text)

        self.assertIn("private vulnerability reporting", security)
        self.assertIn("@mili-xi", codeowners)
        self.assertIn("not affiliated with or endorsed", readme)

    def test_impact_document_uses_honest_evidence_language(self):
        impact = self.read("docs/impact.md")
        self.assertEqual(impact.count("<!-- release-metrics:start -->"), 1)
        self.assertEqual(impact.count("<!-- release-metrics:end -->"), 1)
        self.assertIn("cumulative download events", impact)
        self.assertIn("not unique users", impact)
        self.assertIn("None recorded", impact)
        self.assertIn("repository remains private", impact)

    def test_codex_application_blocks_are_bounded_and_factual(self):
        doc = self.read("docs/CODEX_FOR_OSS_APPLICATION.md")
        for lang in ("zh", "en"):
            for field in ("qualification", "api-credits", "additional-notes"):
                pattern = (
                    rf"<!-- codex:{lang}:{field}:start -->\s*"
                    rf"(.+?)"
                    rf"\s*<!-- codex:{lang}:{field}:end -->"
                )
                match = re.search(pattern, doc, flags=re.DOTALL)
                self.assertIsNotNone(match, f"missing {lang}:{field}")
                answer = re.sub(r"\s+", " ", match.group(1)).strip()
                self.assertGreaterEqual(len(answer), 1)
                self.assertLessEqual(len(answer), 500)
                self.assertNotRegex(answer, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
                self.assertNotIn("fabricated", answer.lower())
                self.assertNotIn("guaranteed", answer.lower())

        for required_link in (
            "https://github.com/mili-xi",
            "https://github.com/mili-xi/xun_fei",
            "docs/impact.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
        ):
            self.assertIn(required_link, doc)

    def test_public_documents_do_not_contain_unfinished_markers(self):
        marker_parts = ["T" + "BD", "PLACE" + "HOLDER"]
        public_docs = [
            "README.md",
            "README.zh-CN.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "GOVERNANCE.md",
            "docs/impact.md",
            "docs/CODEX_FOR_OSS_APPLICATION.md",
        ]
        for relative_path in public_docs:
            text = self.read(relative_path)
            for marker in marker_parts:
                self.assertNotIn(marker, text, relative_path)


if __name__ == "__main__":
    unittest.main()
