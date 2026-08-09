# Isolated NAS Ollama

This Compose project runs only Ollama on the NAS. It does not modify NAS users,
home directories, SSH configuration, or system services.

## Security Properties

- Port `11434` is published only on NAS loopback (`127.0.0.1`).
- Ollama cloud features are disabled with `OLLAMA_NO_CLOUD=1`.
- The image is the official, pinned Ollama `0.32.6` digest — no custom build,
  no model weights baked into any image layer.
- The root filesystem is read-only. Only the named model volume and `/tmp` are writable.
- All Linux capabilities are dropped and privilege escalation is disabled.
- Logs rotate instead of growing without a limit.
- Aria receives a 128K operational context window. Single-request concurrency,
  Flash Attention, and Q8 KV cache preserve memory headroom on the 64 GB NAS.

The container still has outbound network access so an operator can pull models.
Port `11434` is published on all NAS interfaces (LAN-reachable, not internet-
exposed) as a deliberate, reversible trade-off: NAS SSH on this appliance does
not support key-based tunneling (no login home directory is provisioned for
any account, and no account has sudo to create one). Revert to loopback-only
plus an SSH tunnel once that platform limitation is resolved (see
tests/unit/test_nas_ollama_compose.py for the enforced port contract). Do not
use host networking.

## Build and Deploy

1. Create the Compose project from `compose.yml` on the NAS and start it.
2. The NAS pulls the pinned `ollama` image itself (digest-verified).
3. A one-shot `model-init` service, running only on the NAS over its internal
   compose network, calls the `ollama` service's own API to pull `qwen3:30b`,
   alias it `aria-primary`, and pull `nomic-embed-text`. It exits once done.
   Nothing is built, staged, or transferred from the Mac — the NAS does its
   own pull with its own CPU/network/storage.

Model: `qwen3:30b` (Qwen3-30B-A3B, MoE — ~3B active params, 19GB, native 256K
context). This exceeds the 128K floor while staying light on NAS CPU/GPU
compute. The operational window is set to 131072 pending the load/latency
benchmark; promotion to the full 256K happens after that benchmark passes.

## Required Verification

From another LAN machine, connection to `<nas-address>:11434` must fail. On the
NAS itself, `curl http://127.0.0.1:11434/api/tags` must succeed. The Mini then
reaches that loopback listener through its restricted SSH tunnel.

References:

- [Ollama Docker documentation](https://docs.ollama.com/docker)
- [Ollama server and local-only configuration](https://docs.ollama.com/faq)
- [Docker Compose service reference](https://docs.docker.com/reference/compose-file/services/)