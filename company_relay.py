import socket, threading, sys, json, signal
import websocket

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 13389
CMD_PORT = 13390
BUFFER = 65536
ROOM = "relay2026"

active_ws = None
active_lock = threading.Lock()

def log(msg):
    print(f"[公司] {msg}", flush=True)

def recv_tpkt(sock):
    buf = b""
    while len(buf) < 4:
        d = sock.recv(4 - len(buf))
        if not d: return None
        buf += d
    if buf[0] == 3:
        need = ((buf[2] << 8) | buf[3]) - 4
        while need > 0:
            d = sock.recv(need)
            if not d: return None
            buf += d
            need -= len(d)
    else:
        d = sock.recv(BUFFER)
        if not d: return None
        buf += d
    return buf

def pipe(src, dst, name):
    log(f"pipe {name} 啟動")
    try:
        while True:
            if isinstance(src, websocket.WebSocket):
                data = src.recv()
                if not data:
                    log(f"pipe {name}: 收到空資料, 結束")
                    break
                if isinstance(data, str):
                    log(f"pipe {name}: 跳過控制訊息")
                    continue
            else:
                data = recv_tpkt(src)
                if not data:
                    log(f"pipe {name}: TCP 收到空資料, 結束")
                    break
            if isinstance(dst, websocket.WebSocket):
                dst.send(data, websocket.ABNF.OPCODE_BINARY)
            else:
                dst.sendall(data)
    except websocket.WebSocketConnectionClosedException:
        log(f"pipe {name}: WebSocket 關閉")
    except Exception as e:
        log(f"pipe {name}: 錯誤 {e}")
    finally:
        for s in (src, dst):
            try: s.close()
            except: pass
    log(f"pipe {name} 結束")

def cmd_listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LOCAL_HOST, CMD_PORT))
    srv.listen(5)
    log(f"指令埠 :{CMD_PORT}")
    while True:
        try:
            conn, addr = srv.accept()
            data = conn.recv(4096)
            cmd_text = data.decode("utf-8", "ignore").strip()
            with active_lock:
                ws = active_ws
            if ws:
                ws.send(cmd_text, websocket.ABNF.OPCODE_TEXT)
                log(f"已傳送指令: {cmd_text}")
                conn.sendall(b"OK\n")
            else:
                conn.sendall(b"ERROR: no active connection\n")
            conn.close()
        except:
            pass

def handle_client(conn, addr):
    global active_ws
    log(f"mstsc 連入 {addr}")
    try:
        ws = websocket.WebSocket(ping_interval=30, enable_multithread=True)
        ws.connect(f"wss://rdp-relay.fly.dev/{ROOM}", timeout=15)
        msg = json.loads(ws.recv())
        role = msg.get("role", "")
        log(f"WebSocket 已連線 (角色: {role})")

        msg2 = json.loads(ws.recv())
        if msg2.get("t") == "peer_on":
            log("外部機已就緒")
        elif msg2.get("t") == "peer_off":
            log("外部機中斷"); ws.close(); return

        with active_lock:
            active_ws = ws

        t1 = threading.Thread(target=pipe, args=(conn, ws, "C->R"), daemon=True)
        t2 = threading.Thread(target=pipe, args=(ws, conn, "R->C"), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
    except Exception as e:
        log(f"失敗: {e}")
    finally:
        with active_lock:
            active_ws = None
        try: conn.close()
        except: pass
    log(f"結束 {addr}")

def main():
    log(f"監聽 :{LOCAL_PORT} (RDP)  指令埠 :{CMD_PORT}")
    log(f"使用: python snc.py <指令>")

    threading.Thread(target=cmd_listener, daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LOCAL_HOST, LOCAL_PORT))
    server.listen(5)

    def shutdown(sig, frame):
        log("結束"); server.close(); sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        try:
            sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(sock, addr), daemon=True).start()
        except:
            break

if __name__ == "__main__":
    main()
