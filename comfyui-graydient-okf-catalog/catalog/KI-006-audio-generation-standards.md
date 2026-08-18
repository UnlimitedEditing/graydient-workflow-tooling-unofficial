---
id: "KI-006"
title: "Audio Generation Standards & Polyphase Resampling"
version: "1.0.0"
type: "specification"
tags:
  - audio-generation
  - audioldm
  - resampling
  - 48khz
sources:
  - "gen_audioldm_t2s.py"
  - "audioldm_l.py"
---

# KI-006: Audio Generation Standards & Polyphase Resampling

## 1. Overview
Audio models like AudioLDM natively synthesize audio at 16kHz (`16000Hz`).
To deliver broadcast-quality, high-fidelity sound for Graydient workflows, output audio should be upsampled to **48kHz (48000Hz)**.

---

## 2. Polyphase Resampling Implementation
Resampling must preserve pitch and playback speed while scaling sample resolution. Use `scipy.signal.resample_poly`:

```python
import math
from scipy import signal

def resample_audio(audio_np, orig_sr=16000, target_sr=48000):
    if orig_sr == target_sr:
        return audio_np
    gcd = math.gcd(int(target_sr), int(orig_sr))
    up = int(target_sr) // gcd
    down = int(orig_sr) // gcd
    return signal.resample_poly(audio_np, up, down)
```

---

## 3. ComfyUI Audio Data Format Standard
Custom audio sampler nodes must return standard ComfyUI audio dictionary objects:

```python
# Convert 1D/2D numpy array to 3D PyTorch float32 tensor [batch, channels, samples]
audio_resampled = resample_audio(raw_audio, 16000, sample_rate)
waveform = torch.from_numpy(audio_resampled).float().unsqueeze(0).unsqueeze(0)

audio_dict = {
    "waveform": waveform,    # 3D PyTorch Tensor [1, 1, samples]
    "sample_rate": sample_rate # Integer (e.g. 48000)
}
return (audio_dict,)
```
