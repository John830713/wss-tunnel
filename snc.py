import socket, sys

CMD_HOST = "127.0.0.1"
CMD_PORT = 13390

def main():
    if len(sys.argv) < 2:
        print("用法: python snc.py <指令>")
        print("指令:")
        print("  pull          - 外部機 git pull")
        print("  deploy        - 外部機 git pull + fly deploy + restart")
        print("  restart       - 外部機重啟 relay")
        print("  exec <命令>   - 外部機執行 shell 命令")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    try:
        s = socket.create_connection((CMD_HOST, CMD_PORT), timeout=5)
        s.sendall(cmd.encode())
        resp = s.recv(4096).decode("utf-8", "ignore")
        print(resp.strip())
        s.close()
    except ConnectionRefusedError:
        print("錯誤: company_relay.py 沒有在執行，或指令埠未就緒")
        sys.exit(1)
    except Exception as e:
        print(f"錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
