from pathlib import Path

import httpx

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample" / "Popeye_forPresident_512kb.mp4"
NAME = "popeye_for_president"
TITLE = "Popeye for President"
FORMAT = "video/mp4"
CONTENT_TYPE = "movie"
DESCRIPTION = """
Popeye and Bluto are both running for president. They are tied with exactly the same number of votes, but Miss Olive Oyl has yet to cast her ballot. Which candidate will be able to impress her the most and earn her precious vote?

Popeye for President March 30 Tom Johnson
Frank Endres Robert Connavale Jack Mercer Seymour Kneitel
In the Public Domain in the United States.
"""
RELEASE_DATE = "1956-03-30"
GENRES = ["cartoon", "animation"]
BASE_URL = "http://localhost:8000"

response = httpx.post(
    f"{BASE_URL}/content",
    json={
        "name": NAME,
        "title": TITLE,
        "format": FORMAT,
        "content_type": CONTENT_TYPE,
        "description": DESCRIPTION,
        "release_date": RELEASE_DATE,
        "genres": GENRES,
    },
)
print(response.status_code)
print(response.json())
response.raise_for_status()
content_id = response.json()["id"]

with open(SAMPLE_PATH, "rb") as f:
    response = httpx.post(
        f"{BASE_URL}/upload/{content_id}",
        content=f,
        headers={"Content-Type": "application/octet-stream"},
        timeout=None,
    )

print(response.status_code)
print(response.json())
