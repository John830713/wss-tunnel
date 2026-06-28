import socket, time

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 13389))
print(f"[trigger] 已連線 company relay :13389")
print(f"[trigger] 保持連線中，按 Ctrl+C 結束")
try:
    while True:
        time.sleep(30)
        sock.send(b"\x00")
except KeyboardInterrupt:
    sock.close()
