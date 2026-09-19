#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${HAJIMI_COMFYUI_ROOT:-/root/ComfyUI}"
RUNTIME_ROOT="${HAJIMI_H3_RUNTIME:-/root/autodl-tmp/hajimi-h3-runtime}"
MODEL_ROOT="${HAJIMI_H3_MODEL_ROOT:-/root/autodl-tmp/ComfyUI-H3-models}"
PYTHON="${HAJIMI_H3_PYTHON:-/root/miniconda3/bin/python}"
LOG_DIR="$RUNTIME_ROOT/logs"
LOG_FILE="$LOG_DIR/comfyui.log"
SESSION="hajimi-h3-comfy"

mkdir -p "$LOG_DIR"
log() { printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG_FILE"; }

if [[ ! -x "$PYTHON" || ! -f "$COMFY_ROOT/main.py" ]]; then
  log "Configured ComfyUI Python or main.py is missing; refusing to start."
  exit 1
fi

required_models=(
  diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
  diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors
  text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
  vae/minimax_h3_video_vae_fp16.safetensors
  vae/minimax_h3_audio_vae_fp32.safetensors
)
for relative in "${required_models[@]}"; do
  if [[ ! -s "$MODEL_ROOT/$relative" ]]; then
    log "Required H3 model is missing or empty: $MODEL_ROOT/$relative"
    exit 1
  fi
  source="$MODEL_ROOT/$relative"
  target="$COMFY_ROOT/models/$relative"
  mkdir -p "$(dirname "$target")"
  if [[ -L "$target" ]]; then
    resolved="$(readlink -f "$target" 2>/dev/null || true)"
    if [[ "$resolved" != "$source" ]]; then
      rm -- "$target"
      ln -s "$source" "$target"
      log "Repaired H3 model symlink: $relative"
    fi
  elif [[ -e "$target" ]]; then
    if [[ ! -f "$target" || "$(stat -c '%s' "$target")" != "$(stat -c '%s' "$source")" ]]; then
      log "Refusing to replace a non-symlink model with a different identity: $target"
      exit 1
    fi
  else
    ln -s "$source" "$target"
    log "Created H3 model symlink: $relative"
  fi
done

if ! "$PYTHON" -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() and torch.cuda.device_count() > 0 else 1)' >/dev/null 2>&1; then
  log "No CUDA device is attached; leaving ComfyUI stopped."
  exit 0
fi

if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 2 http://127.0.0.1:8188/system_stats >/dev/null; then
  log "ComfyUI H3 API is already responding on 127.0.0.1:8188."
  exit 0
fi

run_comfy() {
  cd "$COMFY_ROOT"
  exec "$PYTHON" main.py --listen 127.0.0.1 --port 8188 --preview-method latent2rgb --preview-size 256
}

if command -v screen >/dev/null 2>&1; then
  if screen -ls 2>/dev/null | grep -q "[.]$SESSION"; then
    log "Screen session $SESSION already exists."
    exit 0
  fi
  log "Starting ComfyUI in screen session $SESSION on loopback:8188."
  screen -dmS "$SESSION" bash -lc "cd '$COMFY_ROOT' && exec '$PYTHON' main.py --listen 127.0.0.1 --port 8188 --preview-method latent2rgb --preview-size 256 >> '$LOG_FILE' 2>&1"
  exit 0
fi

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    log "Tmux session $SESSION already exists."
    exit 0
  fi
  log "Starting ComfyUI in tmux session $SESSION on loopback:8188."
  tmux new-session -d -s "$SESSION" "cd '$COMFY_ROOT' && exec '$PYTHON' main.py --listen 127.0.0.1 --port 8188 --preview-method latent2rgb >> '$LOG_FILE' 2>&1"
  exit 0
fi

log "screen/tmux unavailable; running ComfyUI in the calling supervisor process."
run_comfy >> "$LOG_FILE" 2>&1
