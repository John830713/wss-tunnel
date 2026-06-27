# wss-tunnel 外部機自動化

## 初始化

```bash
cd /path/to/wss-tunnel
pip install -r relay/requirements.txt
```

## 啟動 RDP relay

```bash
python external_relay.py
```

## 從公司端接收指令

`company_relay.py` 可透過 WebSocket relay 傳送文字指令過來。
`external_relay.py` 收到指令後自動執行。

支援的指令：
- `pull`     - git pull
- `deploy`   - git pull + fly deploy + 重啟
- `restart`  - 重啟 relay
- `exec ...` - 執行任意 shell 命令

## 更新 relay server

```bash
cd relay
fly deploy
```

## 腳本路徑

- `external_relay.py` - 主要 bridge（RDP 轉送 + 指令接收）
- `relay/main.py`     - Fly.io WebSocket relay server
