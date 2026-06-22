import json
import sys
import urllib.request

URL = "http://localhost:8001/patient/chat"

def send(message, session_id):
    body = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

if __name__ == "__main__":
    session_id = sys.argv[1] if len(sys.argv) > 1 else "test_mhiri_name_1"
    msg = sys.argv[2] if len(sys.argv) > 2 else "I want to book an appointment with Dr MHIRI Kais"
    result = send(msg, session_id)
    mem = result.get("memory", {})
    print("response:", result.get("response"))
    print("step:", mem.get("step"))
    print("intent:", mem.get("intent"))
    print("doctor_id:", mem.get("doctor_id"))
    print("doctor_name:", mem.get("doctor_name"))
    print("specialty:", mem.get("specialty"))
    print("query:", mem.get("query"))
    dr = mem.get("doctor_results")
    if dr:
        print("doctor_results:", [(d.get("id"), d.get("name")) for d in dr])
