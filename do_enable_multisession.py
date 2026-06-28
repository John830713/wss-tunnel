import socket, json, time

# Step 1: Connect to 13389 to trigger WS connection in company_relay
s = socket.create_connection(("127.0.0.1", 13389), timeout=5)
print("[trigger] Connected to 13389, waiting for WS to establish...")
# read_first_tpkt has 3s timeout + ws.connect ~1s + role recv
time.sleep(5)

# Step 2: Send exec command via cmd port 13390
cmd = {
    "cmd": "exec",
    "args": 'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fSingleSessionPerUser /t REG_DWORD /d 0 /f'
}
cmd_text = json.dumps(cmd)
print(f"[send] Sending: {cmd_text}")

c = socket.create_connection(("127.0.0.1", 13390), timeout=3)
c.sendall(cmd_text.encode())
resp = c.recv(4096)
print(f"[response] {resp.decode().strip()}")
c.close()

print("[done] Multi-session RDP should now be enabled")
print("You can now run mstsc and connect to 127.0.0.1:13389")

# Keep trigger alive for a moment
time.sleep(5)
s.close()
