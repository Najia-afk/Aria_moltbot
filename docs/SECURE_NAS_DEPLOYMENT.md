# Secure Mini + NAS Deployment

This deployment keeps Aria's application stack on the Mini, runs inference on a
private NAS, and replicates state to the NAS. Runtime addresses, usernames,
keys, and credentials belong only in `stacks/brain/.env`, which is ignored by
Git.

## Security Boundary

- The Mini exposes only Traefik HTTP/HTTPS on one configured LAN address.
- HTTP redirects to HTTPS. Portal, API, and WebSocket routes require Basic Auth.
- Direct API, web, monitoring, and management ports bind to `127.0.0.1`.
- LiteLLM generates only the NAS chat and embedding routes. Cloud models are
  disabled and cloud keys are not passed to containers.
- NAS backups use key-only SSH, strict host-key checking, checksums, and a
  private remote directory.
- Ollama must be restricted by the NAS firewall to the Mini's source address.
  Prefer a WireGuard/Tailscale address for `NAS_OLLAMA_URL` when available.

## 1. Configure The Mini

```bash
./scripts/configure_secure_lan.sh \
  --nas-host <private-nas-hostname-or-address> \
  --lan-address <mini-lan-address>
```

The script generates missing API credentials, creates the LAN login under
`~/aria_vault/credentials/aria_lan_login`, clears active cloud keys, and keeps a
mode-`0600` copy of the previous environment in the private vault.

Do not add the generated `.env`, login file, private key, TLS key, or backup
content to Git.

## 2. Prepare The NAS

Use the UGREEN administration interface to:

1. Install a vendor-supported Ollama package/container and pin its image version.
2. Store model data on a dedicated NAS volume.
3. Expose Ollama only on the private interface.
4. Add a firewall allow rule for the Mini source address, then deny other sources.
5. Enable SSH for a non-root service account used only for backups.
6. Disable SSH password login only after key login has been tested in a second session.
7. Enable encrypted storage/snapshots for the backup volume when supported.

Select the chat model after checking the NAS CPU/GPU architecture and available
memory. Give the chosen Ollama model the stable alias expected by Aria:

```bash
ollama cp <chosen-chat-model> aria-primary
ollama pull nomic-embed-text
```

The alias keeps hardware-specific model choices out of the public repository.

## 3. Pin SSH Trust

Create a dedicated Ed25519 key locally. Type its passphrase directly into the
terminal; never place a passphrase in `.env` or chat.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/aria_nas_backup -C aria-nas-backup
```

Install only the public key for the NAS backup account. Verify the host-key
fingerprint through the UGREEN UI or physical console before writing it to a
dedicated known-hosts file. Do not rely on `StrictHostKeyChecking=accept-new`.

Add these private values to `stacks/brain/.env`:

```dotenv
NAS_BACKUP_ENABLED=true
NAS_BACKUP_HOST=<private-nas-hostname-or-address>
NAS_BACKUP_USER=<non-root-backup-user>
NAS_BACKUP_PORT=22
NAS_BACKUP_DIR=<absolute-private-backup-directory>
NAS_BACKUP_SSH_KEY=<absolute-private-key-path>
NAS_BACKUP_KNOWN_HOSTS=<absolute-dedicated-known-hosts-path>
```

## 4. Validate And Start

```bash
./scripts/secure_deploy_check.sh
cd stacks/brain
docker compose up -d --build
```

Read the HTTPS port without exposing other environment values:

```bash
grep '^TRAEFIK_HTTPS_PORT=' stacks/brain/.env
```

Open `https://<mini-lan-address>:<https-port>` and use the credentials stored in
`~/aria_vault/credentials/aria_lan_login`. Trust the generated certificate only
after verifying its fingerprint locally.

## 5. Backup And Restore Test

Run one backup manually after the stack is healthy:

```bash
./scripts/aria_backup.sh
```

The script writes database dumps, a memory archive, and `SHA256SUMS`, then
copies and verifies that run on the NAS. A backup is not complete until a test
restore into a disposable database and temporary memory directory succeeds.

## Rollback

If the NAS is unavailable, Aria intentionally fails closed for LLM requests; it
does not send data to a cloud provider. Restore service by repairing the private
NAS route. Application and database recovery use the latest verified local/NAS
backup, while source rollback uses a reviewed Git tag or commit.