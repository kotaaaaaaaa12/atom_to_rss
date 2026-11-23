
"""
AstroArts Atom Feed -> RSS 2.0 Converter

Fetches an Atom feed, converts it to RSS 2.0,
and writes the result to docs/feed.rss.
Designed for scheduled execution with GitHub Actions.
"""

import os
import sys
import time
import tempfile
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Configuration
ATOM_URL = "https://www.astroarts.co.jp/article/feed.atom"

OUTPUT_DIR = Path(__file__).resolve().parent / "docs"
OUTPUT_FILE = OUTPUT_DIR / "feed.rss"

MAX_RETRIES = 3
RETRY_DELAY = 3
REQUEST_TIMEOUT = 30

USER_AGENT = "Mozilla/5.0 (compatible; atom_to_rss/1.0)"

ATOM_NS = "http://www.w3.org/2005/Atom"


def log(message: str):
    """Print a timestamped log message."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] {message}", flush=True)


def fetch_atom_feed(url: str) -> str:
    """Fetch an Atom feed with automatic retries."""

    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/atom+xml, application/xml, text/xml",
        },
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"Fetching Atom feed (attempt {attempt}/{MAX_RETRIES}): {url}")

            with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                status = response.status

                if status != 200:
                    raise RuntimeError(f"Unexpected HTTP status: {status}")

                data = response.read()

                if not data:
                    raise RuntimeError("The server returned an empty response.")

                encoding = response.headers.get_content_charset() or "utf-8"
                content = data.decode(encoding)

                log(f"Download successful ({len(data)} bytes)")
                return content

        except HTTPError as e:
            error = f"HTTP {e.code}: {e.reason}"

            # Retry only temporary server-side or rate-limit errors.
            if e.code not in (408, 425, 429, 500, 502, 503, 504):
                raise RuntimeError(f"Non-retryable HTTP error: {error}") from e

        except (URLError, TimeoutError, ConnectionError, OSError) as e:
            error = str(e)

        except Exception:
            raise

        log(f"Request failed: {error}")

        if attempt < MAX_RETRIES:
            delay = RETRY_DELAY * (2 ** (attempt - 1))
            log(f"Retrying in {delay} seconds...")
            time.sleep(delay)

    raise RuntimeError(
        f"Failed to fetch Atom feed after {MAX_RETRIES} attempts."
    )


def parse_atom_date(date_str: str) -> datetime:
    """Parse an ISO 8601 date into a timezone-aware UTC datetime."""

    date_str = date_str.strip()

    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def atom_to_rss(atom_xml: str) -> str:
    """Convert Atom XML into RSS 2.0 XML."""

    root = ET.fromstring(atom_xml)

    if root.tag != f"{{{ATOM_NS}}}feed":
        raise ValueError("The XML document is not a valid Atom feed.")

    # Channel information
    feed_title = root.findtext(
        f"{{{ATOM_NS}}}title",
        "Untitled Feed"
    )

    feed_link = ""

    for link_el in root.findall(f"{{{ATOM_NS}}}link"):
        if link_el.get("type") == "text/html":
            feed_link = link_el.get("href", "")
            break

    if not feed_link:
        feed_link = ATOM_URL

    feed_updated = root.findtext(
        f"{{{ATOM_NS}}}updated",
        ""
    )

    # Author information
    author_el = root.find(f"{{{ATOM_NS}}}author")
    managing_editor = ""

    if author_el is not None:
        author_name = author_el.findtext(
            f"{{{ATOM_NS}}}name",
            ""
        )

        author_email = author_el.findtext(
            f"{{{ATOM_NS}}}email",
            ""
        )

        if author_email and author_name:
            managing_editor = f"{author_email} ({author_name})"
        elif author_email:
            managing_editor = author_email

    # Build RSS 2.0 XML
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = feed_title
    ET.SubElement(channel, "link").text = feed_link
    ET.SubElement(channel, "description").text = (
        f"{feed_title} - RSS Feed"
    )
    ET.SubElement(channel, "language").text = "ja"
    ET.SubElement(channel, "generator").text = "atom_to_rss converter"

    if feed_updated:
        try:
            dt = parse_atom_date(feed_updated)

            ET.SubElement(channel, "lastBuildDate").text = (
                format_datetime(dt)
            )
        except (ValueError, TypeError):
            log("Warning: Could not parse feed updated date.")

    if managing_editor:
        ET.SubElement(channel, "managingEditor").text = managing_editor

    # Convert entries
    entries = root.findall(f"{{{ATOM_NS}}}entry")

    for entry in entries:
        item = ET.SubElement(channel, "item")

        # Title
        title = entry.findtext(
            f"{{{ATOM_NS}}}title",
            ""
        )

        ET.SubElement(item, "title").text = title

        # Link
        link = ""

        for link_el in entry.findall(f"{{{ATOM_NS}}}link"):
            if link_el.get("rel", "alternate") == "alternate":
                link = link_el.get("href", "")
                break

        ET.SubElement(item, "link").text = link

        # Description
        summary = entry.findtext(
            f"{{{ATOM_NS}}}summary",
            ""
        )

        ET.SubElement(item, "description").text = summary

        # GUID
        entry_id = entry.findtext(
            f"{{{ATOM_NS}}}id",
            link
        )

        guid = ET.SubElement(item, "guid")
        guid.text = entry_id
        guid.set("isPermaLink", "false")

        # Publication date
        updated = entry.findtext(
            f"{{{ATOM_NS}}}updated",
            ""
        )

        if updated:
            try:
                dt = parse_atom_date(updated)

                ET.SubElement(item, "pubDate").text = (
                    format_datetime(dt)
                )
            except (ValueError, TypeError):
                log(f"Warning: Could not parse entry date: {title}")

    # Serialize XML
    ET.indent(rss, space="  ")

    tree = ET.ElementTree(rss)

    from io import BytesIO

    buffer = BytesIO()

    tree.write(
        buffer,
        encoding="utf-8",
        xml_declaration=True
    )

    return buffer.getvalue().decode("utf-8")


def save_rss_atomically(content: str):
    """
    Write RSS to a temporary file and atomically replace
    the existing output only after successful completion.
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=OUTPUT_DIR,
            prefix=".feed-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:

            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, OUTPUT_FILE)

        log(f"RSS output saved: {OUTPUT_FILE}")

    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

        raise


def main():
    log("Starting Atom to RSS conversion.")

    # Fetch Atom
    atom_xml = fetch_atom_feed(ATOM_URL)

    # Convert Atom to RSS
    log("Converting Atom XML to RSS 2.0.")

    rss_xml = atom_to_rss(atom_xml)

    log(f"Conversion completed ({len(rss_xml)} characters).")

    # Save output
    save_rss_atomically(rss_xml)

    log("Conversion completed successfully.")


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        log("Process interrupted.")
        sys.exit(130)

    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
