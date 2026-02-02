# MLX Server Setup for Aria

MLX is Apple's ML framework optimized for Apple Silicon. It provides native GPU acceleration without Docker overhead.

## Model

**Primary Model**: `nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx`
- Architecture: Qwen3-VLTO 8B (Text-Only version of Vision-Language model)
- Quantization: qx86x-hi (8-bit with group size 32)
- RAM Usage: ~6-7GB
- Strengths: Good reasoning, instruction following, tool support

## Installation

```bash
# Install MLX-LM
pip3 install --upgrade mlx-lm

# Download model (will cache in ~/.cache/huggingface/)
python3 -m huggingface_hub.commands.huggingface_cli download nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx

# Test manually
python3 -m mlx_lm.server --model nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx --host 0.0.0.0 --port 8080
```

## Automatic Startup (launchd)

The service is configured via `~/Library/LaunchAgents/com.aria.mlx-server.plist`.

```bash
# Load service
launchctl load ~/Library/LaunchAgents/com.aria.mlx-server.plist

# Check status
launchctl list | grep aria

# View logs
tail -f /tmp/mlx_server.log
tail -f /tmp/mlx_server.err

# Restart
launchctl stop com.aria.mlx-server
launchctl start com.aria.mlx-server

# Unload (disable)
launchctl unload ~/Library/LaunchAgents/com.aria.mlx-server.plist
```

## API Endpoint

- **URL**: `http://localhost:8080/v1`
- **Format**: OpenAI-compatible
- **Models endpoint**: `GET /v1/models`
- **Chat endpoint**: `POST /v1/chat/completions`

### Test Command

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

## LiteLLM Integration

In `litellm-config.yaml`:
```yaml
- model_name: qwen3-mlx
  litellm_params:
    model: openai/nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx
    api_base: http://host.docker.internal:8080/v1
    api_key: not-needed
```

## Disabling Ollama

Ollama should be disabled when using MLX to free up RAM:

```bash
# Stop Ollama
pkill -f ollama
killall Ollama

# Disable autostart
launchctl unload ~/Library/LaunchAgents/com.ollama.ollama.plist
```

## Performance Notes

- First request is slow (model loading into GPU memory)
- Subsequent requests are fast
- Memory stays allocated until server restart
- M4 Mac Mini can run 8B models comfortably
