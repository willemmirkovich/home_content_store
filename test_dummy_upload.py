import requests

NAME = "dummy"
FORMAT = "mp4"

dummy_bytes = b"\x00" * 1024

response = requests.post(
    "http://localhost:8000/upload",
    params={"name": NAME, "format": FORMAT},
    data=dummy_bytes,
    headers={"Content-Type": "application/octet-stream"},
)

print(response.status_code)
print(response.json())
