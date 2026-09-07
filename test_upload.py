import requests

# MOV_PATH = "static/knicks_bar.mov"
# NAME = "Knicks Bar Video 5"
# FORMAT = "video/quicktime"
MOV_PATH = "test/lilo_and_stich.mp4"
NAME = "Lilo and Stich"
FORMAT = "video/mp4"

with open(MOV_PATH, "rb") as f:
    response = requests.post(
        f"http://localhost:8000/upload",
        params={"name": NAME, "format": FORMAT, "description": "test things out"},
        data=f,
        headers={"Content-Type": "application/octet-stream"},
    )

print(response.status_code)
print(response.json())
