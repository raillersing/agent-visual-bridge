"""Open the durable French qualification guide without submitting any decision."""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_visual_bridge.browser import open_browser_session  # noqa: E402
from agent_visual_bridge.sessions import ReviewService  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "reports" / "qualification-guide")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    directory = args.directory.absolute()
    directory.mkdir(parents=True, exist_ok=True)
    proposal = json.loads((ROOT / "examples/qualification/guide.fr.json").read_text(encoding="utf-8"))
    database = directory / "reviews.sqlite3"
    service = ReviewService(database)
    review_id = proposal["review_id"]
    if not any(row["id"] == review_id for row in service.list_reviews()):
        service.create_review(proposal)
        service.settings(proposal["project_id"], {"preferences": {"language": "fr", "detail": "full"}})
    session = open_browser_session(database, review_id, lease_seconds=86400)
    print(json.dumps({"url": session["url"], "review_id": review_id,
                      "database": str(database), "access_hours": 24}, ensure_ascii=False), flush=True)
    if args.open_browser:
        webbrowser.open(session["url"])


if __name__ == "__main__":
    main()
