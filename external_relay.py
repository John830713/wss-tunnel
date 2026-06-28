import socket, threading, sys, json, time, subprocess, os
import websocket

RDP_HOST = os.environ.get("RDP_HOST", "127.0.0.1")
RDP_PORT = int(os.environ.get("RDP_PORT", "3389"))
BUFFER = 65536
ROOM = "relay2026v2"

def log(msg):
    print(f"[外部] {msg}", flush=True)

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

def handle_cmd(text, rdp_sock):
    try:
        cmd = json.loads(text)
    except:
        return
    if "t" in cmd and cmd["t"] in ("role", "peer_on", "peer_off"):
        return
    t = cmd.get("cmd", "")
    args = cmd.get("args", "")
    log(f"收到指令: {t} {args}")

    if t == "pull":
        log("執行 git pull...")
        r = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30)
        log(r.stdout.strip() or r.stderr.strip() or "(完成)")
    elif t == "deploy":
        log("執行 deploy...")
        r = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30)
        log(r.stdout.strip())
        r2 = subprocess.run(["fly", "deploy"], capture_output=True, text=True, timeout=120)
        log(r2.stdout.strip() or r2.stderr.strip() or "(完成)")
    elif t == "restart":
        log("重新啟動...")
        rdp_sock.close()
        os._exit(0)
    elif t == "exec":
        log(f"執行: {args}")
        r = subprocess.run(args, shell=True, capture_output=True, text=True, timeout=60)
        log(r.stdout.strip() or r.stderr.strip() or "(完成)")
    else:
        log(f"未知指令: {t}")

def ws_to_rdp(ws, rdp):
    try:
        n = 0
        while True:
            msg = ws.recv()
            if not msg: break
            if isinstance(msg, bytes):
                if n < 3:
                    log(f"收到 RDP 資料: {len(msg)} bytes {msg[:32].hex()}")
                    n += 1
                rdp.sendall(msg)
            elif isinstance(msg, str):
                handle_cmd(msg, rdp)
    except Exception as e:
        log(f"ws→rdp 錯誤: {e}")
    finally:
        for s in (ws, rdp):
            try: s.close()
            except: pass

def rdp_to_ws(rdp, ws):
    try:
        while True:
            data = recv_tpkt(rdp)
            if not data: break
            ws.send(data, websocket.ABNF.OPCODE_BINARY)
    except Exception as e:
        log(f"rdp→ws 錯誤: {e}")
    finally:
        for s in (rdp, ws):
            try: s.close()
            except: pass

def main():
    url = f"wss://rdp-relay.fly.dev/{ROOM}"
    log(f"目標: {url}")

    while True:
        try:
            log("正在連線 WebSocket...")
            ws = websocket.WebSocket(ping_interval=30, enable_multithread=True)
            ws.connect(url, timeout=30)
            msg = json.loads(ws.recv())
            role = msg.get("role", "")
            log(f"已連線 (角色: {role})")

            log(f"正在連線 RDP {RDP_HOST}:{RDP_PORT}...")
            rdp = socket.create_connection((RDP_HOST, RDP_PORT), timeout=10)
            rdp.settimeout(None)
            log("RDP 已連線，開始轉送")

            t1 = threading.Thread(target=ws_to_rdp, args=(ws, rdp), daemon=True)
            t2 = threading.Thread(target=rdp_to_ws, args=(rdp, ws), daemon=True)
            t1.start(); t2.start()
            t1.join()
            log("ws→rdp pipe 結束")
            t2.join(timeout=3)
            log("連線中斷，10 秒後重連")
            ws.close()
            time.sleep(10)
        except Exception as e:
            log(f"錯誤: {e}")
            try: ws.close()
            except: pass
            time.sleep(10)

if __name__ == "__main__":
    main()
