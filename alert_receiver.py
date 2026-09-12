import uvicorn
from fastapi import FastAPI, Request
import json
import logging
import sys

app = FastAPI()

log = logging.getLogger("uvicorn.access")
log.setLevel(logging.CRITICAL)

@app.post("/alert")
async def receive_alert(request: Request):
    payload = await request.json()
    
    print("\n\n" + "🔴"*30)
    print("🚨 [AGENTOPS CRITICAL ALERT TRIGGERED] 🚨")
    print("🔴"*30)
    print("Grafana just detected a system anomaly in the Agent!")
    print("="*60)
    
    try:
        alerts = payload.get("alerts", [])
        for alert in alerts:
            status = alert.get("status", "unknown").upper()
            summary = alert.get("annotations", {}).get("summary", "Unknown Failure")
            print(f"Status: {status} | Detail: {summary}")
    except:
        pass
        
    print("="*60 + "\n\n")
    sys.stdout.flush()
    return {"status": "Alert Received!"}

if __name__ == "__main__":
    print("AgentOps Local Alert Receiver running on http://localhost:5050/alert")
    uvicorn.run(app, host="0.0.0.0", port=5050, access_log=False)
