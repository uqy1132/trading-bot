import sys
print("HELLO FROM PYTHON", flush=True)
print(f"Python: {sys.version}", flush=True)

import os
print(f"GROQ_API_KEY exists: {'GROQ_API_KEY' in os.environ}", flush=True)
print(f"DISCORD_WEBHOOK_URL exists: {'DISCORD_WEBHOOK_URL' in os.environ}", flush=True)

# Test Discord langsung tanpa import scheduler
import requests
webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
if webhook:
    r = requests.post(webhook, json={"content": "✅ GitHub Actions test!"}, verify=False)
    print(f"Discord status: {r.status_code}", flush=True)
else:
    print("ERROR: DISCORD_WEBHOOK_URL kosong!", flush=True)