#!/usr/bin/env python3
"""
Bulk HTML Downloader
- Input: list of URLs (via args or a file)
- Output: saves each page's HTML to disk in a single run (with concurrency, retries, and sane filenames)
Requires: requests
"""
import argparse
import os
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import time

try:
    import requests
except ImportError as e:
    print("This script requires the 'requests' package. Install it with: pip install requests", file=sys.stderr)
    sys.exit(1)

DEFAULT_UA = "bulk-html-downloader/1.0 (+https://example.invalid)"
SAFE_CHAR_RE = re.compile(r"[^A-Za-z0-9._-]+")

def safe_filename_from_url(url: str, max_len: int = 180) -> str:
    """
    Turn a URL into a filesystem-safe filename.
    Example: https://example.com/a/b/ -> example.com_a_b_index.html
    """
    parsed = urlparse(url)
    netloc = parsed.netloc or "unknown"
    path = parsed.path or ""
    if not path or path.endswith("/"):
        path = path + "index"
    # include query if present (hashed) to avoid collisions
    q = parsed.query
    suffix = ""
    if q:
        import hashlib
        suffix = "_" + hashlib.sha1(q.encode("utf-8")).hexdigest()[:10]
    raw = f"{netloc}{path}{suffix}"
    # replace separators with underscores and strip weird chars
    raw = raw.replace("/", "_")
    raw = SAFE_CHAR_RE.sub("_", raw)
    # ensure extension
    if not re.search(r"\.(html?|xhtml)$", raw, re.IGNORECASE):
        raw = raw + ".html"
    # limit length safely
    if len(raw) > max_len:
        base, ext = os.path.splitext(raw)
        raw = base[: max_len - len(ext)] + ext
    return raw

def uniquify_path(path: Path) -> Path:
    """Append -1, -2, ... if file already exists."""
    if not path.exists():
        return path
    base = path.stem
    ext = path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f"{base}-{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1

def fetch_one(session: requests.Session, url: str, out_dir: Path, timeout: float, retries: int, backoff: float, verbose: bool) -> dict:
    """Download a single URL with simple retry/backoff. Returns dict with status and path or error."""
    headers = {"User-Agent": DEFAULT_UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            # Only save if it's HTML-ish
            ctype = resp.headers.get("Content-Type", "")
            if "text/html" not in ctype and "application/xhtml+xml" not in ctype and not resp.text.strip().lower().startswith("<!doctype html"):
                return {"url": url, "ok": False, "error": f"Non-HTML content-type: {ctype}"}
            resp.raise_for_status()
            fname = safe_filename_from_url(url)
            out_path = uniquify_path(out_dir / fname)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(resp.content)
            if verbose:
                print(f"[OK] {url} -> {out_path}", file=sys.stderr)
            return {"url": url, "ok": True, "path": str(out_path)}
        except requests.RequestException as e:
            last_err = str(e)
            if attempt < retries:
                sleep_s = backoff ** attempt
                if verbose:
                    print(f"[Retry {attempt+1}/{retries}] {url}: {last_err} (sleep {sleep_s:.2f}s)", file=sys.stderr)
                time.sleep(sleep_s)
            else:
                if verbose:
                    print(f"[FAIL] {url}: {last_err}", file=sys.stderr)
                return {"url": url, "ok": False, "error": last_err}
    return {"url": url, "ok": False, "error": last_err or "Unknown error"}

def read_urls_from_file(path: Path) -> list:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Download multiple HTML pages in one run.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--urls", nargs="+", help="URLs to download (space-separated).")
    src.add_argument("--urls-file", type=str, help="Path to a text file with one URL per line.")
    p.add_argument("--out-dir", type=str, default="downloaded_html", help="Output directory.")
    p.add_argument("--concurrency", type=int, default=10, help="Number of parallel downloads.")
    p.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds.")
    p.add_argument("--retries", type=int, default=2, help="Number of retry attempts on failure.")
    p.add_argument("--backoff", type=float, default=2.0, help="Exponential backoff base (seconds^attempt).")
    p.add_argument("--verbose", action="store_true", help="Print per-URL results to stderr.")
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    urls = args.urls if args.urls else read_urls_from_file(Path(args.urls_file))
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            deduped.append(u)
            seen.add(u)
    if not deduped:
        print("No URLs to process.", file=sys.stderr)
        return 1

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=args.concurrency, pool_maxsize=args.concurrency, max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(fetch_one, session, url, out_dir, args.timeout, args.retries, args.backoff, args.verbose): url for url in deduped}
        for fut in as_completed(futures):
            results.append(fut.result())

    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]
    print(f"Downloaded {len(ok)}/{len(results)} pages to: {out_dir}")
    if fail:
        print("Failed URLs:", file=sys.stderr)
        for r in fail:
            print(f" - {r['url']}: {r.get('error','unknown error')}", file=sys.stderr)
    return 0 if not fail else 2

if __name__ == "__main__":
    raise SystemExit(main())
