import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


SPEC = importlib.util.spec_from_file_location(
    "sync_global", Path(__file__).resolve().parents[1] / "scripts/sync_global.py"
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def rules(count, prefix="example"):
    return b"# rules\n" + b"".join(
        f"DOMAIN-SUFFIX,{prefix}{i}.test\n".encode() for i in range(count)
    )


class Response:
    def __init__(self, status=200, body=b"", headers=None):
        self.status, self.body, self.headers = status, body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.destination = self.root / "Global.list"
        self.old = rules(30_000)
        self.destination.write_bytes(self.old)
        self.curated = self.root / "global-fix.list"
        self.curated.write_bytes(b"hand-maintained exclusions and deduplication\n")
        self.ai = self.root / "AI.list"
        self.ai.write_bytes(b"hand-maintained Apple Intelligence rules\n")

    def assert_preserved(self):
        self.assertEqual(self.destination.read_bytes(), self.old)
        self.assertEqual(self.curated.read_bytes(), b"hand-maintained exclusions and deduplication\n")
        self.assertEqual(self.ai.read_bytes(), b"hand-maintained Apple Intelligence rules\n")
        self.assertEqual(list(self.root.glob(".Global.list.sync-*")), [])

    def test_error_and_challenge_pages_do_not_replace(self):
        for page in [b"<html>error</html>", b"Just a moment...", b"# cf-chl-token", b"<!DOCTYPE html>"]:
            with self.subTest(page=page):
                with self.assertRaises(sync.SyncError):
                    sync.sync(self.root, lambda: page)
                self.assert_preserved()

    def test_every_noncomment_line_is_validated(self):
        for bad in [b"error page\n", b"DOMAIN-SUFFIX,foo.test,DIRECT\n", b"IP-CIDR,999.1.1.1/24\n", b"DOMAIN-SUFFIX,https://bad.test\n", b"IP-CIDR6,1.1.1.0/24\n", b"IP-CIDR,1.1.1.0/24,unknown\n", b"DOMAIN-SUFFIX,-bad.test\n", b"AND,((DOMAIN,foo.test))\n"]:
            with self.subTest(bad=bad):
                with self.assertRaises(sync.SyncError):
                    sync.sync(self.root, lambda: self.old + bad)
                self.assert_preserved()

    def test_count_drop_below_ratio_is_rejected(self):
        with self.assertRaisesRegex(sync.SyncError, "range"):
            sync.sync(self.root, lambda: rules(23_999))
        self.assert_preserved()

    def test_count_spike_is_rejected(self):
        with self.assertRaisesRegex(sync.SyncError, "range"):
            sync.sync(self.root, lambda: rules(37_501))
        self.assert_preserved()

    def test_minimum_and_duplicate_padding(self):
        for candidate in [rules(19_999), b"DOMAIN-SUFFIX,one.test\n" * 30_000]:
            with self.assertRaisesRegex(sync.SyncError, "Too few"):
                sync.sync(self.root, lambda: candidate)
            self.assert_preserved()

    def test_unchanged_does_not_replace_or_touch_mtime(self):
        before = self.destination.stat()
        with patch.object(sync.os, "replace") as replace:
            self.assertFalse(sync.sync(self.root, lambda: self.old))
            replace.assert_not_called()
        self.assertEqual(before.st_mtime_ns, self.destination.stat().st_mtime_ns)
        self.assert_preserved()

    def test_valid_rules_replace_only_global_atomically(self):
        candidate = rules(30_001)
        self.destination.chmod(0o640)
        real_replace = sync.os.replace
        with patch.object(sync.os, "replace", wraps=real_replace) as replace:
            self.assertTrue(sync.sync(self.root, lambda: candidate))
            self.assertEqual(replace.call_count, 1)
            staged, target = replace.call_args.args
            self.assertEqual(staged.parent, target.parent)
        self.assertEqual(self.destination.read_bytes(), candidate)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.curated.read_bytes(), b"hand-maintained exclusions and deduplication\n")
        self.assertEqual(self.ai.read_bytes(), b"hand-maintained Apple Intelligence rules\n")

    def test_html_previous_file_uses_verified_recovery_count(self):
        self.destination.write_bytes(b"<html>Just a moment</html>")
        with self.assertRaisesRegex(sync.SyncError, "range"):
            sync.sync(self.root, lambda: rules(22_000))
        self.assertEqual(self.destination.read_bytes(), b"<html>Just a moment</html>")
        self.assertTrue(sync.sync(self.root, lambda: rules(sync.BOOTSTRAP_RULES)))

    def test_filter_preserves_comments_line_endings_and_only_excludes_com(self):
        candidate = rules(30_000).replace(b"\n", b"\r\n")
        filtered, _ = sync.validate(candidate + b" domain-suffix , COM \r\n")
        self.assertEqual(filtered, candidate)

    def test_supported_ip_and_domain_grammar(self):
        for line in ["DOMAIN,foo.test", "DOMAIN-SUFFIX,example.test", "DOMAIN-KEYWORD,foo-", "USER-AGENT,OneDrive*", "IP-CIDR,1.1.1.0/24,no-resolve", "IP-CIDR6,2606:4700::/32", "IP-ASN,4134,no-resolve", "GEOIP,CN"]:
            sync.rule_key(line, 1)

    def test_bad_encoding_size_and_null_are_rejected(self):
        for body in [b"\xff", b"\0", b"x" * (sync.MAX_BYTES + 1)]:
            with self.assertRaises(sync.SyncError):
                sync.validate(body)

    def test_download_failure_cleans_up_and_preserves_previous(self):
        with self.assertRaises(sync.SyncError):
            sync.sync(self.root, lambda: (_ for _ in ()).throw(sync.SyncError("download failed")))
        self.assert_preserved()

    def test_destination_symlink_is_rejected(self):
        self.destination.unlink()
        self.destination.symlink_to(self.curated)
        with self.assertRaises(sync.SyncError):
            sync.sync(self.root, lambda: self.old)
        self.assertEqual(self.curated.read_bytes(), b"hand-maintained exclusions and deduplication\n")

    def test_exact_200_and_plain_content_required(self):
        for response in [Response(204), Response(206), Response(200, headers={"Content-Type": "text/html"}), Response(200, headers={"cf-mitigated": "challenge"})]:
            with self.subTest(status=response.status, headers=response.headers):
                with patch.object(sync, "urlopen", return_value=response):
                    with self.assertRaises(sync.SyncError):
                        sync.fetch()
        with patch.object(sync, "urlopen", return_value=Response(200, self.old)):
            self.assertEqual(sync.fetch(), self.old)

    def test_http_and_network_errors_are_sanitized(self):
        for error in [HTTPError("private-url", 403, "Forbidden", {}, None), HTTPError("private-url", 500, "error", {}, None), URLError("private-url"), TimeoutError("private-url")]:
            with patch.object(sync, "urlopen", side_effect=error):
                with self.assertRaises(sync.SyncError) as raised:
                    sync.fetch()
                self.assertNotIn("private-url", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
