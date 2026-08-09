# Isolated NAS Ollama

This Compose project runs only Ollama on the NAS. It does not modify NAS users,
home directories, SSH configuration, or system services.

## Security Properties

- Port `11434` is published only on NAS loopback (`127.0.0.1`).
- Ollama cloud features are disabled with `OLLAMA_NO_CLOUD=1`.
- The image must be supplied as an immutable digest; floating tags are rejected.
- The root filesystem is read-only. Only the named model volume and `/tmp` are writable.
- All Linux capabilities are dropped and privilege escalation is disabled.
- Logs rotate instead of growing without a limit.

The container still has outbound network access so an operator can pull models.
Do not publish port `11434` on a LAN address and do not use host networking.

## UGREEN Deployment

1. Open the UGREEN **Docker** application.
2. Create a Compose project and upload `compose.yml`.
3. Create the project environment variable `OLLAMA_IMAGE` with a reviewed,
   immutable value such as `ollama/ollama@sha256:<verified-digest>`.
4. Create/start the project and confirm the container becomes healthy.
5. Use the UGREEN container terminal to pull and alias the selected models:

```bash
ollama pull <reviewed-chat-model>
ollama cp <reviewed-chat-model> aria-primary
ollama pull nomic-embed-text
ollama list
```

Model selection must follow a NAS CPU/GPU benchmark. The 64 GB system-memory
figure alone does not establish that a large model will run at useful speed.

## Required Verification

From another LAN machine, connection to `<nas-address>:11434` must fail. On the
NAS itself, `curl http://127.0.0.1:11434/api/tags` must succeed. The Mini then
reaches that loopback listener through its restricted SSH tunnel.

References:

- [Ollama Docker documentation](https://docs.ollama.com/docker)
- [Ollama server and local-only configuration](https://docs.ollama.com/faq)
- [Docker Compose service reference](https://docs.docker.com/reference/compose-file/services/)