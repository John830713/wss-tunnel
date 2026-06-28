import socket, sys, time, json

cmd_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "help"

# Connect to 13389 to trigger WS (so active_ws gets set)
s = socket.create_connection(("127.0.0.1", 13389), timeout=5)

# Wait for WS connection to establish (read_first_tpkt 3s + ws.connect)
time.sleep(5)

# Send command via 13390
c = socket.create_connection(("127.0.0.1", 13390), timeout=3)
c.sendall(cmd_text.encode())
resp = c.recv(4096)
print(resp.decode().strip())
c.close()
time.sleep(2)
s.close()
