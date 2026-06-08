# Deployment

How to run RemoteToolbox on a home server and reach it from your phone. Aimed at
a typical Linux box (a NUC, a Pi 5, an old laptop, a homelab VM).

## 1. Prerequisites

- **Python 3.10+**
- **[Ollama](https://ollama.com)** installed and running, with a tool-capable
  model pulled:

  ```bash
  curl -fsSL https://ollama.com/install.sh | sh   # Linux
  ollama pull llama3.1                             # or qwen2.5, mistral-nemo, ...
  ollama serve                                     # usually already running as a service
  ```

  Tool calling needs a model that supports it. Good small choices: `llama3.1`
  (8B), `qwen2.5`, `mistral-nemo`. Bigger = better tool use, if your hardware
  allows.

## 2. Install RemoteToolbox

```bash
git clone https://github.com/theklic/RemoteToolbox.git
cd RemoteToolbox
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[telegram]"          # add ,mcp if you use external MCP servers
```

## 3. Configure

```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=<from @BotFather>
RTB_ALLOWED_USERS=<your Telegram user ID from @userinfobot>
OLLAMA_HOST=http://localhost:11434
```

Edit `config.yaml`: set `chat.adapter: telegram` and pick your `llm.ollama.model`.

## 4. Add tools and test locally first

```bash
cp -r examples/tools/system_info tools/system_info
```

Verify with the **console adapter** before going remote (set
`chat.adapter: console` temporarily, or keep a second config):

```bash
python -m remotetoolbox
```

Ask it "how much disk space is free?" — confirm the tool fires. Then switch
`adapter` back to `telegram`.

## 5. Create the Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`, follow prompts.
2. Copy the token into `.env` as `TELEGRAM_BOT_TOKEN`.
3. Message [@userinfobot](https://t.me/userinfobot) to get your numeric user ID;
   put it in `RTB_ALLOWED_USERS`.
4. Run `python -m remotetoolbox` and message your bot.

> The bot uses **long-polling** — it connects out to Telegram. You do **not**
> need a public IP, port forwarding, or a reverse proxy. This is the simplest
> and safest way to get remote access from anywhere.

## 6. Run it as a service (systemd)

So it survives reboots and restarts on crash. Create
`/etc/systemd/system/remotetoolbox.service`:

```ini
[Unit]
Description=RemoteToolbox
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/RemoteToolbox
ExecStart=/home/youruser/RemoteToolbox/.venv/bin/python -m remotetoolbox
Restart=on-failure
RestartSec=5
# Optional hardening:
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now remotetoolbox
journalctl -u remotetoolbox -f          # follow logs
```

## 7. Docker (alternative)

A minimal `Dockerfile` (not shipped — add one if you prefer containers):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[telegram]"
CMD ["python", "-m", "remotetoolbox"]
```

Mount your gitignored `tools/`, `.env`, and `config.yaml` at runtime so they
aren't baked into the image:

```bash
docker run --rm \
  -v "$PWD/tools:/app/tools" \
  -v "$PWD/.env:/app/.env" \
  -v "$PWD/config.yaml:/app/config.yaml" \
  --network host \
  remotetoolbox
```

(`--network host` lets the container reach Ollama on `localhost:11434`; adjust
`OLLAMA_HOST` if your model server lives elsewhere.)

## Updating / changing tools

Tools load **at startup**. After editing or adding a tool:

```bash
sudo systemctl restart remotetoolbox      # or Ctrl-C + rerun in dev
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Could not reach Ollama…" | `ollama serve` not running, or wrong `OLLAMA_HOST`. |
| Bot replies "⛔ Not authorized." | Your user ID isn't in `RTB_ALLOWED_USERS`. |
| Bot ignores everyone | Allowlist is empty (safe default) — add your ID. |
| Model never calls tools | Model doesn't support tool calling — switch models. |
| Tool not found | File outside `tools.paths`, named with `_`, or import error (check logs). |
| Tool changes don't apply | You didn't restart the process. |
