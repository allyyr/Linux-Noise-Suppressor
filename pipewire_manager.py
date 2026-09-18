"""
Manages the PipeWire filter-chain config that routes a real microphone
through the RNNoise LADSPA plugin into a virtual "Noise Suppressed
Microphone" source that other apps (Discord, Zoom, OBS...) can select.

This does NOT talk to PipeWire's audio graph directly at the C API level —
it generates a config file that PipeWire's built-in filter-chain module
reads on startup, then restarts the user's PipeWire services to apply it.
That's a deliberate simplicity trade-off: it means toggling suppression
on/off briefly interrupts all audio (a second or two), but it avoids
writing and maintaining a native PipeWire client, which is a much bigger
undertaking. See README for the "next steps" note on hot-reloading instead.
"""

import json
import os
import subprocess
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "pipewire" / "pipewire.conf.d"
CONFIG_FILE = CONFIG_DIR / "99-noise-suppressor.conf"

SETTINGS_DIR = Path.home() / ".config" / "noise-suppressor"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# Common install locations for librnnoise_ladspa.so across distros.
LADSPA_SEARCH_PATHS = [
    "/usr/lib/ladspa/librnnoise_ladspa.so",
    "/usr/lib/x86_64-linux-gnu/ladspa/librnnoise_ladspa.so",
    "/usr/lib64/ladspa/librnnoise_ladspa.so",
    "/usr/local/lib/ladspa/librnnoise_ladspa.so",
]


def find_ladspa_plugin() -> str | None:
    for path in LADSPA_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None


def list_audio_sources() -> list[tuple[str, str]]:
    """
    Returns [(source_name, human_description), ...] for real input devices,
    excluding monitor sources and any source this app already created.
    """
    try:
        raw = subprocess.check_output(
            ["pactl", "-f", "json", "list", "sources"], text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    sources = []
    for entry in json.loads(raw):
        name = entry.get("name", "")
        if name.endswith(".monitor") or name == "rnnoise_source":
            continue
        description = entry.get("description", name)
        sources.append((name, description))
    return sources


def build_config(source_name: str, plugin_path: str, vad_threshold: float) -> str:
    """
    vad_threshold: 0-100. Higher = more aggressive noise gating (may clip
    quiet speech); lower = gentler (may let more noise through).
    """
    return f"""context.modules = [
{{  name = libpipewire-module-filter-chain
    args = {{
        node.description = "Noise Suppressed Microphone"
        media.name = "Noise Suppressed Microphone"
        filter.graph = {{
            nodes = [
                {{
                    type = ladspa
                    name = rnnoise
                    plugin = {plugin_path}
                    label = noise_suppressor_mono
                    control = {{
                        "VAD Threshold (%)" = {vad_threshold}
                        "VAD Grace Period (ms)" = 200
                        "Retroactive VAD Grace (ms)" = 0
                    }}
                }}
            ]
        }}
        capture.props = {{
            node.name = "capture.rnnoise_source"
            node.target = "{source_name}"
            audio.channels = 1
            audio.position = [ MONO ]
        }}
        playback.props = {{
            node.name = "rnnoise_source"
            media.class = Audio/Source
            audio.channels = 1
            audio.position = [ MONO ]
        }}
    }}
}}
]
"""


def is_enabled() -> bool:
    return CONFIG_FILE.exists()


def enable(source_name: str, vad_threshold: float) -> tuple[bool, str]:
    plugin_path = find_ladspa_plugin()
    if not plugin_path:
        return False, (
            "Couldn't find librnnoise_ladspa.so. Install the RNNoise LADSPA "
            "plugin for your distro first — see README."
        )

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(build_config(source_name, plugin_path, vad_threshold))

    ok, msg = _restart_pipewire()
    if not ok:
        return False, msg
    return True, "Noise suppression enabled. Select 'Noise Suppressed Microphone' in your apps."


def disable() -> tuple[bool, str]:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    ok, msg = _restart_pipewire()
    if not ok:
        return False, msg
    return True, "Noise suppression disabled."


def _restart_pipewire() -> tuple[bool, str]:
    try:
        subprocess.run(
            ["systemctl", "--user", "restart", "pipewire", "pipewire-pulse", "wireplumber"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, "ok"
    except subprocess.CalledProcessError as e:
        return False, f"Failed to restart PipeWire services: {e.stderr}"
    except FileNotFoundError:
        return False, "systemctl not found — is this a systemd-based distro?"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"source_name": "", "vad_threshold": 50.0, "enabled": False}


def save_settings(settings: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
