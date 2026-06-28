import socket, threading, sys, json, signal, time
import websocket

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 13389
CMD_PORT = 13390
BUFFER = 65536
ROOM = "relay2026v2"
XOR_KEY = 0x55

active_ws = None
active_lock = threading.Lock()

def log(msg):
    print(f"[公司] {msg}", flush=True)

def xor(data):
    return bytes(b ^ XOR_KEY for b in data)

def fix_req(data):
    if len(data) >= 19 and data[0] == 3 and data[4] == 0x0e:
        return data[:16] + b'\x00\x00\x00'
    return data

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
    peer_gone_since = None
    try:
        while True:
            if isinstance(src, websocket.WebSocket):
                src.settimeout(5)
                try:
                    data = src.recv()
                except websocket.WebSocketTimeoutException:
                    if peer_gone_since is not None and time.time() - peer_gone_since > 30:
                        log(f"pipe {name}: 對方已中斷超過 30 秒，結束")
                        break
                    continue
                if not data:
                    log(f"pipe {name}: 收到空資料, 結束")
                    break
                if isinstance(data, str):
                    if '"t": "result"' in data:
                        try:
                            r = json.loads(data)
                            print(f"[外部結果] {r.get('data', '')}", flush=True)
                        except:
                            pass
                        continue
                    if '"peer_off"' in data:
                        log(f"pipe {name}: 外部機中斷，等待重連...")
                        peer_gone_since = time.time()
                        continue
                    if '"peer_on"' in data:
                        log(f"pipe {name}: 外部機已重新連線")
                        peer_gone_since = None
                        continue
                if isinstance(dst, socket.socket):
                    data = xor(data)
            else:
                data = recv_tpkt(src)
                if not data:
                    log(f"pipe {name}: TCP 收到空資料, 結束")
                    break
                if isinstance(dst, websocket.WebSocket):
                    data = xor(fix_req(data))
            if isinstance(dst, websocket.WebSocket):
                dst.send(data, websocket.ABNF.OPCODE_BINARY)
            else:
                dst.sendall(data)
            if peer_gone_since is not None:
                peer_gone_since = time.time()
    except websocket.WebSocketConnectionClosedException:
        log(f"pipe {name}: WebSocket 關閉")
    except Exception as e:
        log(f"pipe {name}: 錯誤 {e}")
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

def read_first_tpkt(conn, timeout=3):
    """Try to read first TPKT packet from socket with timeout."""
    conn.settimeout(timeout)
    try:
        data = recv_tpkt(conn)
        conn.settimeout(None)
        return data
    except socket.timeout:
        conn.settimeout(None)
        return None

def handle_client(conn, addr):
    global active_ws
    log(f"mstsc 連入 {addr}")

    # Try to read initial RDP data synchronously
    first = read_first_tpkt(conn)
    if first:
        log(f"讀取到初始資料 {len(first)} bytes: {first[:32].hex()}")

    try:
        ws = websocket.WebSocket(ping_interval=30, enable_multithread=True)
        ws.connect(f"wss://rdp-relay.fly.dev/{ROOM}", timeout=30)
        role = json.loads(ws.recv()).get("role", "")
        log(f"WebSocket 已連線 (角色: {role})")
        log("外部機已就緒")

        with active_lock:
            active_ws = ws

        if first:
            log(f"傳送緩衝 {len(first)} bytes: {first[:32].hex()}")
            ws.send(xor(fix_req(first)), websocket.ABNF.OPCODE_BINARY)
        elif role == "b":
            log("等待外部機傳送初始資料...")

        t1 = threading.Thread(target=pipe, args=(conn, ws, "C->R"), daemon=True)
        t2 = threading.Thread(target=pipe, args=(ws, conn, "R->C"), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
    except Exception as e:
        log(f"失敗: {e}")
    finally:
        with active_lock:
            if active_ws is ws:
                active_ws = None
        try: conn.close()
        except: pass
        try: ws.close()
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
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        try:
            sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(sock, addr), daemon=True).start()
        except KeyboardInterrupt:
            log("結束"); break
        except:
            break

if __name__ == "__main__":
    main()
