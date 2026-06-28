import socket, sys, time

cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "help"

# Connect to 13389 to trigger WS
s = socket.create_connection(("127.0.0.1", 13389), timeout=5)
time.sleep(0.5)

# Send command via 13390
c = socket.create_connection(("127.0.0.1", 13390), timeout=3)
c.sendall(cmd.encode())
resp = c.recv(4096)
print("Response:", resp.decode().strip())
c.close()
time.sleep(2)
s.close()
