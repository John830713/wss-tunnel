import socket, threading, sys, json, time, subprocess, os, signal, select
import websocket

RDP_HOST = os.environ.get("RDP_HOST", "127.0.0.1")
RDP_PORT = int(os.environ.get("RDP_PORT", "3389"))
BUFFER = 65536
ROOM = "relay2026v2"
XOR_KEY = 0x55

def log(msg):
    print(f"[外部] {msg}", flush=True)

log("啟動版本 2026-06-28")

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

def handle_cmd(text, rdp_sock):
    try:
        cmd = json.loads(text)
        t = cmd.get("cmd", "")
        args = cmd.get("args", "")
    except:
        t = text.strip()
        args = ""
    if t in ("role", "peer_on", "peer_off"):
        return
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

def ws_to_rdp(ws, rdp, rdp_err):
    try:
        n = 0
        while True:
            msg = ws.recv()
            if not msg: break
            if isinstance(msg, bytes):
                dec = xor(msg)
                dec = fix_req(dec)
                if n < 3:
                    log(f"收到 RDP 資料: {len(msg)} bytes {dec[:32].hex()}")
                    n += 1
                try:
                    rdp.sendall(dec)
                except Exception as e:
                    log(f"RDP 寫入錯誤: {e}")
                    rdp_err.set()
                    raise
            elif isinstance(msg, str):
                handle_cmd(msg, rdp)
    except Exception as e:
        if not rdp_err.is_set():
            log(f"ws→rdp 錯誤: {e}")
    finally:
        try: ws.close()
        except: pass

def recv_tpkt_timeout(sock, timeout=60):
    buf = b""
    while len(buf) < 4:
        ready = select.select([sock], [], [], timeout)
        if not ready[0]:
            return None
        d = sock.recv(4 - len(buf))
        if not d: return None
        buf += d
    if buf[0] == 3:
        need = ((buf[2] << 8) | buf[3]) - 4
        while need > 0:
            ready = select.select([sock], [], [], timeout)
            if not ready[0]:
                return None
            d = sock.recv(need)
            if not d: return None
            buf += d
            need -= len(d)
    else:
        d = sock.recv(65536)
        if not d: return None
        buf += d
    return buf

def rdp_to_ws(rdp, ws, rdp_err):
    try:
        n = 0
        while True:
            data = recv_tpkt_timeout(rdp)
            if not data: break
            enc = xor(data)
            if n < 3:
                log(f"rdp→ws 送出: {len(enc)} bytes {enc[:32].hex()}")
                n += 1
            try:
                ws.send(enc, websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                log(f"WS 寫入錯誤: {e}")
                raise
    except Exception as e:
        if not rdp_err.is_set():
            log(f"rdp→ws 錯誤: {e}")

def main():
    url = f"wss://rdp-relay.fly.dev/{ROOM}"
    log(f"目標: {url}")

    def shutdown(sig, frame):
        log("結束"); sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        try:
            log(f"正在連線 RDP {RDP_HOST}:{RDP_PORT}...")
            rdp = socket.create_connection((RDP_HOST, RDP_PORT), timeout=10)
            rdp.settimeout(None)
            log("RDP 已連線")
        except Exception as e:
            log(f"RDP 連線失敗: {e}")
            time.sleep(10)
            continue

        ws_fail = 0
        while True:
            try:
                log("正在連線 WebSocket...")
                ws = websocket.WebSocket(ping_interval=30, enable_multithread=True)
                ws.connect(url, timeout=30)
                msg = json.loads(ws.recv())
                role = msg.get("role", "")
                log(f"已連線 (角色: {role})")
                ws_fail = 0

                rdp_err = threading.Event()
                log("開始轉送")
                t1 = threading.Thread(target=ws_to_rdp, args=(ws, rdp, rdp_err), daemon=True)
                t2 = threading.Thread(target=rdp_to_ws, args=(rdp, ws, rdp_err), daemon=True)
                t1.start(); t2.start()
                t1.join()
                log("ws→rdp pipe 結束（3 秒後重連 WebSocket）")
                t2.join(timeout=3)
                ws.close()

                if rdp_err.is_set():
                    log("RDP 連線已中斷，重新連線 RDP")
                    rdp.close()
                    time.sleep(3)
                    break

                time.sleep(3)
            except Exception as e:
                log(f"WebSocket 錯誤: {e}")
                try: ws.close()
                except: pass
                ws_fail += 1
                if ws_fail >= 3:
                    log("WebSocket 連續失敗太多次，重新連線 RDP")
                    time.sleep(3)
                    break
                time.sleep(3)

if __name__ == "__main__":
    main()
