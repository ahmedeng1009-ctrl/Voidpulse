import urllib.request, json, os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("PEXELS_API_KEY")
print("Key:", key[:15] + "...")

url = "https://api.pexels.com/videos/search?query=dark+night&orientation=portrait&per_page=5&size=medium"
req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "VoidPulse/1.0"})

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    videos = data.get("videos", [])
    print(f"Videos found: {len(videos)}")
    for v in videos[:3]:
        files = v.get("video_files", [])
        for f in files[:5]:
            print(f"  quality={f.get('quality')} type={f.get('file_type')} link={f.get('link','')[:50]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
