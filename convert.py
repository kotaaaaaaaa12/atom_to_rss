"""
AstroArts Atom Feed → RSS 2.0 変換スクリプト

Atomフィードを取得してRSS 2.0形式のXMLに変換し、docs/feed.rss として出力する。
GitHub Actionsで定期実行する想定。
"""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.request import Request, urlopen

ATOM_URL = "https://www.astroarts.co.jp/article/feed.atom"
OUTPUT_DIR = Path(__file__).resolve().parent / "docs"
OUTPUT_FILE = OUTPUT_DIR / "feed.rss"

# Atom名前空間
ATOM_NS = "http://www.w3.org/2005/Atom"


def fetch_atom_feed(url: str) -> str:
    """AtomフィードのXMLを取得して返す。"""
    req = Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; atom_to_rss/1.0)")
    req.add_header("Accept", "application/atom+xml, application/xml, text/xml")
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_atom_date(date_str: str) -> datetime:
    """Atom形式の日時文字列 (ISO 8601) をdatetimeに変換。"""
    # "2026-07-07T09:57:24Z" のような形式
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # フォールバック: fromisoformat
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def atom_to_rss(atom_xml: str) -> str:
    """Atom XMLをRSS 2.0 XML文字列に変換する。"""
    root = ET.fromstring(atom_xml)

    # --- チャンネル情報の抽出 ---
    feed_title = root.findtext(f"{{{ATOM_NS}}}title", "Untitled Feed")

    # feedのlink (type="text/html" のもの)
    feed_link = ""
    for link_el in root.findall(f"{{{ATOM_NS}}}link"):
        if link_el.get("type") == "text/html":
            feed_link = link_el.get("href", "")
            break
    if not feed_link:
        feed_link = ATOM_URL

    feed_updated = root.findtext(f"{{{ATOM_NS}}}updated", "")

    # author情報
    author_el = root.find(f"{{{ATOM_NS}}}author")
    managing_editor = ""
    if author_el is not None:
        author_name = author_el.findtext(f"{{{ATOM_NS}}}name", "")
        author_email = author_el.findtext(f"{{{ATOM_NS}}}email", "")
        if author_email and author_name:
            managing_editor = f"{author_email} ({author_name})"
        elif author_email:
            managing_editor = author_email

    # --- RSS 2.0のXML構築 ---
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = feed_title
    ET.SubElement(channel, "link").text = feed_link
    ET.SubElement(channel, "description").text = f"{feed_title} - RSS Feed"
    ET.SubElement(channel, "language").text = "ja"
    ET.SubElement(channel, "generator").text = "atom_to_rss converter"

    if feed_updated:
        try:
            dt = parse_atom_date(feed_updated)
            ET.SubElement(channel, "lastBuildDate").text = format_datetime(dt)
        except Exception:
            pass

    if managing_editor:
        ET.SubElement(channel, "managingEditor").text = managing_editor

    # --- エントリの変換 ---
    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        item = ET.SubElement(channel, "item")

        # title
        title = entry.findtext(f"{{{ATOM_NS}}}title", "")
        ET.SubElement(item, "title").text = title

        # link
        link = ""
        for link_el in entry.findall(f"{{{ATOM_NS}}}link"):
            if link_el.get("rel", "alternate") == "alternate":
                link = link_el.get("href", "")
                break
        ET.SubElement(item, "link").text = link

        # description (Atomのsummary)
        summary = entry.findtext(f"{{{ATOM_NS}}}summary", "")
        ET.SubElement(item, "description").text = summary

        # guid
        entry_id = entry.findtext(f"{{{ATOM_NS}}}id", link)
        guid = ET.SubElement(item, "guid")
        guid.text = entry_id
        guid.set("isPermaLink", "false")

        # pubDate
        updated = entry.findtext(f"{{{ATOM_NS}}}updated", "")
        if updated:
            try:
                dt = parse_atom_date(updated)
                ET.SubElement(item, "pubDate").text = format_datetime(dt)
            except Exception:
                pass

    # --- XML出力 ---
    ET.indent(rss, space="  ")
    tree = ET.ElementTree(rss)

    # 文字列として返す
    from io import BytesIO

    buf = BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


def main():
    print(f"Atomフィード取得中: {ATOM_URL}")
    atom_xml = fetch_atom_feed(ATOM_URL)
    print(f"取得完了 ({len(atom_xml)} bytes)")

    rss_xml = atom_to_rss(atom_xml)
    print(f"RSS 2.0変換完了 ({len(rss_xml)} bytes)")

    # 出力ディレクトリ作成 & 書き込み
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(rss_xml, encoding="utf-8")
    print(f"出力完了: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
