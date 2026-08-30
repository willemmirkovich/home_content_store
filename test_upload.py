import requests

MOV_PATH = "static/knicks_bar.mov"
NAME = "knicks_bar"
FORMAT = "mov"

with open(MOV_PATH, "rb") as f:
    response = requests.post(
        f"http://localhost:8000/upload",
        params={"name": NAME, "format": FORMAT},
        data=f,
        headers={"Content-Type": "application/octet-stream"},
    )

print(response.status_code)
print(response.json())
