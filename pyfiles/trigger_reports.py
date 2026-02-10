import requests
import json
import time

# 配置
BASE_URL = "http://127.0.0.1:8000"
# 请根据实际数据库中有数据的日期修改这里
PAYLOAD = {
    "start_date": "2023-11-01", 
    "end_date": "2023-11-07" 
}

endpoints = [
    "/report/part1_overview",
    "/report/part2_hazards",
    "/report/part3_trends",
    "/report/part4_skylight"
]

print(f"Testing API at {BASE_URL} with date range: {PAYLOAD['start_date']} to {PAYLOAD['end_date']}")
print("-" * 50)

success_count = 0

for ep in endpoints:
    url = f"{BASE_URL}{ep}"
    print(f"Calling {ep} ... ", end="", flush=True)
    try:
        resp = requests.post(url, json=PAYLOAD)
        if resp.status_code == 200:
            print("✅ Success")
            success_count += 1
            # Optional: Print first few chars of response
            # print(str(resp.json())[:100] + "...")
        else:
            print(f"❌ Failed (Status: {resp.status_code})")
            print(f"   Error: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("   (Make sure api_server.py is running)")

print("-" * 50)
if success_count == len(endpoints):
    print("🎉 All endpoints called successfully!")
    print("📂 JSON files should now appear in the api_server.py directory.")
else:
    print(f"⚠️  {success_count}/{len(endpoints)} requests succeeded.")
