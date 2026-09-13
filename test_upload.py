import requests

MOV_PATH = "static/knicks_bar.mov"
NAME = "knick_bar_video"
TITLE = "Knicks Bar Video"
FORMAT = "video/quicktime"
CONTENT_TYPE = "recording"

# MOV_PATH = "test/lilo_and_stich.mp4"
# NAME = "lilo_and_stich"
# TITLE = "Lilo and Stich"
# FORMAT = "video/mp4"
# CONTENT_TYPE = "movie"

with open(MOV_PATH, "rb") as f:
    response = requests.post(
        f"http://localhost:8000/upload",
        params={
            "name": NAME,
            "format": FORMAT,
            "title": TITLE,
            "content_type": CONTENT_TYPE,
            "description": "test things out"
        },
        data=f,
        headers={"Content-Type": "application/octet-stream"},
    )

print(response.status_code)
print(response.json())
