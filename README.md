# Linux Noise Suppressor

A lightweight Linux desktop app that reduces microphone background noise in
real time using **RNNoise**, **LADSPA**, and **PipeWire** — free, local,
no cloud, no subscription. The Linux equivalent of Krisp.

The app provides a GUI to pick a microphone, adjust suppression strength,
and create a virtual **Noise Suppressed Microphone** that other apps
(Discord, Zoom, OBS, browsers, anything with a mic dropdown) can select as
their input.

## Features

- 🎙️ Select an available microphone
- 🔇 Reduce background noise using RNNoise
- 🎚️ Adjust the VAD threshold from the GUI
- 🔊 Create a virtual `Noise Suppressed Microphone`
- ⚙️ Automatically configure PipeWire
- 🔄 Enable/disable suppression from the app
- 🖥️ PySide6 desktop interface
- 📌 System tray support
- 💾 Save microphone and suppression settings

## Architecture

The app doesn't process audio itself in Python — that would be too slow for
real-time voice. Instead, it generates a **PipeWire filter-chain config**
that routes the microphone through the RNNoise LADSPA plugin natively:

```text
Physical Microphone
        │
        ▼
     PipeWire
        │
        ▼
 RNNoise LADSPA
        │
        ▼
Noise Suppressed Microphone
        │
        ├── Discord
        ├── Zoom
        ├── OBS
        └── Other applications
```

PipeWire and RNNoise do the actual audio processing; the Python app is a
control panel that writes config and manages the plugin, not part of the
live audio path.

## Technologies

- **Python 3**
- **PySide6** — desktop GUI
- **PipeWire** — Linux audio system
- **PipeWire filter-chain** — audio processing pipeline
- **RNNoise** — neural-network-based noise suppression
- **LADSPA** — audio plugin interface
- **PulseAudio compatibility layer** — device discovery via `pactl`
- **VMware** — current development/testing environment

## Project structure

```text
noise-suppression-for-voice/
│
├── app/
│   ├── main.py
│   └── pipewire_manager.py
│
├── external/
│   └── rnnoise/
│
├── build/
│   └── bin/
│       └── ladspa/
│           └── librnnoise_ladspa.so
│
└── venv/
```

## Installation

### 1. System dependencies (Ubuntu)

```bash
sudo apt update
sudo apt install \
    git \
    cmake \
    pkg-config \
    python3 \
    python3-venv \
    ladspa-sdk \
    libx11-dev \
    libxext-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libfreetype6-dev \
    libasound2-dev \
    libcurl4-openssl-dev
```

### 2. Build the RNNoise LADSPA plugin

```bash
git clone --recursive https://github.com/werman/noise-suppression-for-voice
cd noise-suppression-for-voice
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make
```

Plugin ends up at `build/bin/ladspa/librnnoise_ladspa.so`. Install it:

```bash
sudo mkdir -p /usr/lib/ladspa
sudo cp bin/ladspa/librnnoise_ladspa.so /usr/lib/ladspa/
```

Verify:

```bash
find /usr/lib/ladspa -name "librnnoise_ladspa.so"
# expected: /usr/lib/ladspa/librnnoise_ladspa.so
```

### 3. Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install PySide6==6.7.2
```

## Running

```bash
source venv/bin/activate
cd app
python3 main.py
```

Select your microphone, adjust the suppression threshold, and enable
suppression. This creates a virtual **Noise Suppressed Microphone** device
that other apps can pick as their input.

## How it works internally

When suppression is enabled, `pipewire_manager.py`:

1. Detects the RNNoise LADSPA plugin on disk.
2. Generates a PipeWire filter-chain config file.
3. Routes the selected microphone into the RNNoise filter.
4. Creates the virtual audio source.
5. Restarts the user's PipeWire services to apply it.
6. Exposes the processed mic to other applications.

Config file: `~/.config/pipewire/pipewire.conf.d/99-noise-suppressor.conf`
App settings: `~/.config/noise-suppressor/settings.json`

## Suppression strength

Exposed as a VAD threshold, 0–100%. Higher = more aggressive gating (risk of
cutting quiet speech); lower = more permissive (risk of letting noise
through). Default: **50%**. The right value depends on your mic and room.

## Current status

### ✅ Working

- RNNoise LADSPA plugin built successfully from source
- Plugin installed under `/usr/lib/ladspa`
- PipeWire installed and running, with PulseAudio compatibility enabled
- Python virtual environment configured
- PySide6 GUI running
- Microphone selection interface implemented
- PipeWire filter-chain config generation implemented
- Virtual microphone creation logic implemented

### ⚠️ Current VM limitation

The app depends on the OS exposing a physical microphone through PipeWire.
In the current VMware test environment, only `auto_null.monitor` is
exposed — no physical `alsa_input` microphone source yet. Microphone input
needs to be enabled in VMware's sound-card settings before the app can
detect and process it. **This is an environment/VM config gap, not a bug in
the app itself** — the build, plugin, and GUI logic are all confirmed
working up to the point of needing a real mic source to route.

## Next steps

- Hot-reload PipeWire config without restarting audio services (avoids the
  brief audio interruption on toggle)
- Better microphone/device error handling
- Automatic detection of VMware/USB audio devices
- Packaging for Ubuntu and other distros (Flatpak is the strongest option
  for cross-distro reach)
- Autostart on login
- Improved system-tray controls
- Presets for different noise environments (office, outdoors, etc.)
- More advanced RNNoise control exposure (grace periods, not just VAD
  threshold)

## License

This project uses RNNoise/LADSPA components from the underlying open-source
noise-suppression ecosystem. Refer to the respective upstream projects for
their licenses and attribution requirements.
