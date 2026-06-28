import socket, time, sys, json

def send_cmd(cmd_text):
    try:
        c = socket.create_connection(("127.0.0.1", 13390), timeout=2)
        c.sendall(cmd_text.encode())
        resp = c.recv(4096)
        r = resp.decode().strip()
        c.close()
        return r
    except Exception as e:
        return f"error: {e}"

# Build JSON command
if len(sys.argv) < 2:
    print("Usage: deploy.py <cmd> [args]")
    sys.exit(1)

t = sys.argv[1]
args = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
cmd_json = json.dumps({"cmd": t, "args": args})

print(f"Sending JSON: {cmd_json}")

# Start mstsc connection to trigger WS
s = socket.create_connection(("127.0.0.1", 13389), timeout=10)
print(f"[{time.time():.0f}] Connected to 13389, waiting for WS...")
time.sleep(3)

for i in range(30):
    r = send_cmd(cmd_json)
    print(f"[{time.time():.0f}] #{i+1}: {r}")
    if "OK" in r and "no active" not in r:
        print("Command accepted!")
        break
    time.sleep(2)

s.close()
print("Done")
