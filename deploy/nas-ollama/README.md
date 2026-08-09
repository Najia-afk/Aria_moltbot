# Isolated NAS Ollama

This Compose project runs only Ollama on the NAS. It does not modify NAS users,
home directories, SSH configuration, or system services.

## Security Properties

- Port `11434` is published only on NAS loopback (`127.0.0.1`).
- Ollama cloud features are disabled with `OLLAMA_NO_CLOUD=1`.
- The reviewed Ollama `0.32.6` multi-platform image is pinned by immutable digest.
- The root filesystem is read-only. Only the named model volume and `/tmp` are writable.
- All Linux capabilities are dropped and privilege escalation is disabled.
- Logs rotate instead of growing without a limit.
- Aria receives a 128K operational context window. Single-request concurrency,
  Flash Attention, and Q8 KV cache preserve memory headroom on the 64 GB NAS.

The container still has outbound network access so an operator can pull models.
Do not publish port `11434` on a LAN address and do not use host networking.

## UGREEN Deployment

1. Open the UGREEN **Docker** application.
2. Create a Compose project and upload `compose.yml`.
3. Create/start the project and confirm the container becomes healthy.
4. Use the UGREEN container terminal to pull and alias the selected models:

```bash
ollama pull <reviewed-chat-model>
ollama cp <reviewed-chat-model> aria-primary
ollama pull nomic-embed-text
ollama list
```

Model selection must follow a NAS CPU/GPU benchmark. The 64 GB system-memory
figure alone does not establish that a large model will run at useful speed.
Qwen3.5 is natively 256K, but its own guidance recommends retaining at least
128K for thinking quality. The initial release therefore uses 128K and promotes
to 256K only after load, latency, and memory tests pass.

## Required Verification

From another LAN machine, connection to `<nas-address>:11434` must fail. On the
NAS itself, `curl http://127.0.0.1:11434/api/tags` must succeed. The Mini then
reaches that loopback listener through its restricted SSH tunnel.

References:

- [Ollama Docker documentation](https://docs.ollama.com/docker)
- [Ollama server and local-only configuration](https://docs.ollama.com/faq)
- [Docker Compose service reference](https://docs.docker.com/reference/compose-file/services/)