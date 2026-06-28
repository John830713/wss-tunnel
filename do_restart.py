import json, socket, time

def send_cmd(cmd_text):
    for i in range(30):
        try:
            c = socket.create_connection(("127.0.0.1", 13390), timeout=3)
            c.sendall(cmd_text.encode())
            resp = c.recv(4096).decode().strip()
            c.close()
            if resp != "ERROR: no active connection":
                return resp
        except:
            pass
        time.sleep(1)
    return "Timeout"

# Step 1: Trigger WS connection
s = socket.create_connection(("127.0.0.1", 13389), timeout=5)
time.sleep(1)

# Step 2: Start new relay window with updated code
cmd1 = json.dumps({"cmd": "exec", "args": 'start "Ext Relay v2" python D:\\wss-tunnel\\external_relay.py'})
print("1. Starting new relay...")
r1 = send_cmd(cmd1)
print(f"   Response: {r1}")

# Wait for new relay to connect RDP + WS
print("2. Waiting 10s for new relay...")
time.sleep(10)

# Step 3: Kill old relay
cmd2 = json.dumps({"cmd": "restart"})
print("3. Killing old relay...")
r2 = send_cmd(cmd2)
print(f"   Response: {r2}")

time.sleep(5)
s.close()
print("Done - new relay (v2) should be running")
