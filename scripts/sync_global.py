#!/usr/bin/env python3
"""Validate and atomically sync the upstream mirror, never curated rule files.

Global.list is an upstream mirror. global-fix.list and AI.list are maintained
by hand and must not be derived from it. New upstream rule types fail closed
until their grammar is reviewed here; the observed upstream uses domain,
IP and User-Agent rules. No response body, URL, or credentials are printed.
"""

import ipaddress
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


UPSTREAM = "https://yfamilys.com/rule/Global.list"
MIN_RULES = 20_000
MIN_RATIO = 0.80
MAX_RATIO = 1.25
MAX_BYTES = 8 * 1024 * 1024
# All Global.list versions in available Git history are challenge pages.
# Recovery anchor: the manually validated HTTP-200 upstream snapshot on
# 2026-11-07 (SHA-256 below), after the explicit DOMAIN-SUFFIX,com exclusion.
# The March pre-curation copy is too old to serve as today's size baseline.
# This is only a count: curated files are NEVER read or rewritten by sync.
BOOTSTRAP_RULES = 49_076
BOOTSTRAP_SOURCE_SHA256 = "1ea5e57a8db7362365cd7cbe105265ec0a09d8dd4519326fc8880f20798cf27f"
CHALLENGE = re.compile(
    r"<\s*(?:!doctype\s+html|html\b|head\b|body\b|script\b)|"
    r"cf-chl|just\s+a\s+moment|cloudflare\s+challenge",
    re.IGNORECASE,
)


class SyncError(ValueError):
    pass


def valid_domain(value):
    if not value or len(value) > 253 or value.endswith("."):
        return False
    try:
        labels = value.encode("idna").decode("ascii").split(".")
    except UnicodeError:
        return False
    return all(
        0 < len(label) <= 63
        and re.fullmatch(r"[a-zA-Z0-9_](?:[a-zA-Z0-9_-]*[a-zA-Z0-9_])?", label)
        for label in labels
    )


def rule_key(line, number):
    """Validate the admitted policy-free Loon subscription grammar."""
    fields = [part.strip() for part in line.split(",")]
    if len(fields) < 2 or not all(fields):
        raise SyncError(f"Invalid rule at line {number}")
    kind, value, *options = fields
    kind = kind.upper()
    if kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
        valid = not options and valid_domain(value)
        value = value.lower()
    elif kind == "DOMAIN-KEYWORD":
        valid = not options and bool(re.fullmatch(r"[a-zA-Z0-9_.-]+", value))
        value = value.lower()
    elif kind == "USER-AGENT":
        # Loon supports wildcard User-Agent matches. This upstream's values
        # are single tokens; refuse controls, embedded policies and markup.
        valid = not options and bool(re.fullmatch(r"[a-zA-Z0-9_.%*?+-]+", value))
    elif kind in {"IP-CIDR", "IP-CIDR6"}:
        valid = options in ([], ["no-resolve"])
        try:
            network = ipaddress.ip_network(value, strict=True)
            valid = valid and "/" in value and network.version == (
                4 if kind == "IP-CIDR" else 6
            )
            value = str(network)
        except ValueError:
            valid = False
    elif kind == "IP-ASN":
        valid = (
            options in ([], ["no-resolve"])
            and value.isascii() and value.isdecimal()
            and 0 < int(value) <= 4_294_967_295
        )
    elif kind == "GEOIP":
        valid = options in ([], ["no-resolve"]) and bool(
            re.fullmatch(r"[a-zA-Z]{2}", value)
        )
        value = value.upper()
    else:
        # In particular, do not accept HTML, arbitrary text, policy-bearing
        # rules, or a logical/regex expression without a dedicated validator.
        raise SyncError(f"Unreviewed rule type at line {number}")
    if not valid:
        raise SyncError(f"Invalid rule at line {number}")
    return (kind, value, *options)


def validate(body):
    if len(body) > MAX_BYTES or b"\x00" in body:
        raise SyncError("Response size or encoding is invalid")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeError:
        raise SyncError("Response is not UTF-8") from None
    if CHALLENGE.search(text):
        raise SyncError("HTML or challenge response rejected")
    unique = set()
    output = []
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key = rule_key(stripped, number)
            # Preserve the original sync's explicit exclusion, including
            # harmless case/whitespace variants. Do not derive global-fix.
            if key == ("DOMAIN-SUFFIX", "com"):
                continue
            unique.add(key)
        output.append(line)
    if len(unique) < MIN_RULES:
        raise SyncError(f"Too few unique valid rules ({len(unique)})")
    return "".join(output).encode("utf-8"), len(unique)


def fetch():
    request = Request(UPSTREAM, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://yfamilys.com/",
    })
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise SyncError(f"Expected HTTP 200, received {response.status}")
            if "html" in response.headers.get("Content-Type", "").lower():
                raise SyncError("HTML content type rejected")
            if response.headers.get("cf-mitigated", "").lower() == "challenge":
                raise SyncError("Challenge response header rejected")
            return response.read(MAX_BYTES + 1)
    except HTTPError as error:
        raise SyncError(f"Expected HTTP 200, received {error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise SyncError("Upstream download failed") from None


def sync(repository, download=fetch):
    # The sole writable destination is deliberately not configurable.
    destination = Path(repository) / "Global.list"
    if destination.is_symlink():
        raise SyncError("Refusing a symlink destination")
    previous = destination.read_bytes() if destination.exists() else b""
    try:
        _, baseline = validate(previous)
        baseline_source = "previous valid Global.list"
    except SyncError:
        baseline = BOOTSTRAP_RULES
        baseline_source = "verified recovery snapshot count (previous file invalid)"
    temporary = None
    try:
        # Stage on the same filesystem, validate the staged bytes, then rename.
        with tempfile.NamedTemporaryFile(
            prefix=".Global.list.sync-", dir=destination.parent, delete=False
        ) as staged:
            temporary = Path(staged.name)
            staged.write(download())
            staged.flush()
            os.fsync(staged.fileno())
        candidate, count = validate(temporary.read_bytes())
        if not baseline * MIN_RATIO <= count <= baseline * MAX_RATIO:
            raise SyncError(
                f"Rule count outside 80%-125% range ({count} vs {baseline})"
            )
        print(f"Validated {count} unique rules; baseline: {baseline_source}")
        if candidate == previous:
            print("No changes")
            return False
        temporary.write_bytes(candidate)
        mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644
        temporary.chmod(mode)
        with temporary.open("rb") as staged:
            os.fsync(staged.fileno())
        os.replace(temporary, destination)
        print("Updated Global.list atomically; curated files untouched")
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    try:
        sync(Path(__file__).resolve().parents[1])
    except (SyncError, OSError) as error:
        # Do not include download bodies/URLs or OS paths in Actions logs.
        message = str(error) if isinstance(error, SyncError) else "Filesystem operation failed"
        print(f"Sync failed: {message}. Global.list retained.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
