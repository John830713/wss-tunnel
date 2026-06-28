import socket, sys, time, json

cmd_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "help"

# Connect to 13389 to trigger WS (so active_ws gets set)
s = socket.create_connection(("127.0.0.1", 13389), timeout=5)

# Wait for WS connection to establish with retries
for attempt in range(30):
    try:
        c = socket.create_connection(("127.0.0.1", 13390), timeout=3)
        c.sendall(cmd_text.encode())
        resp = c.recv(4096).decode().strip()
        c.close()
        if resp != "ERROR: no active connection":
            print(resp)
            break
    except:
        pass
    time.sleep(1)
else:
    print("ERROR: timeout waiting for WS connection")

time.sleep(2)
s.close()
