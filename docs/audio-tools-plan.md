# AudioTools Plugin Implementation Plan

## Goals

- Provide per-device equalizer controls for both playback (output) and recording (input) devices.
- Allow users to manage presets per source, including save, load, delete, and default selection.
- Enable high-quality audio recording (e.g., system loopback such as Spotify) to WAV with configurable quality and metadata editing.
- Ensure cross-platform support for Windows and Linux with graceful fallbacks when specific APIs are unavailable.

## Progress Update

- Equalizer and recorder tabs are scaffolded with device selectors, preset management, and quality dialog placeholders.
- Config schema now persists per-device presets and recorder settings with sensible defaults and migration helpers.
- Initial unit tests cover equalizer state transitions, preset lifecycle, and recorder configuration defaults.
- Recorder workflow now includes a start/stop-ready backend: real captures via `sounddevice` when available, with a silent placeholder fallback for headless environments.
- A `MMST_AUDIO_PLACEHOLDER=1` override keeps automated tests deterministic by forcing the silent writer.

## Work Breakdown

### 1. Core Services & Utilities

- [x] Add `AudioDeviceService` to `mmst.core.services` exposing:
  - `list_playback_devices()` / `list_capture_devices()` returning IDs, friendly names, capabilities.
  - `observe_device_changes(callback)` placeholder for future hotplug support.
- [ ] Implement Windows backend using `pycaw` (WASAPI) for playback and loopback capture.
- [ ] Implement Linux backend using `pulsectl` (PulseAudio) with optional PipeWire integration.
- [ ] Provide pure-Python fallback that exposes default system device when specific backends unavailable.

### 2. Config Schema

- [x] Define config structure under `audio_tools` with keys for `devices`, `eq.presets`, and `recorder` quality settings.
- [x] Implement migration helper to ensure defaults exist when plugin starts.

### 3. UI Structure

- [x] Equalizer tab layout (device selector, 10-band sliders, preset toolbar, spectrum meter placeholder).
- [x] Recorder tab layout (source selector, record/stop button, meter, metadata dialog trigger, quality settings dialog).
- [ ] Shared status bar and notification hooks.

### 4. Equalizer Engine

- [ ] Integrate per-device DSP pipeline (start with Windows WASAPI loopback + `scipy.signal`).
- [ ] Provide simulation mode for unsupported platforms (apply EQ to sample audio for preview, display warning).
- [x] Persist current slider values and active preset to config store on change.
- [x] Implement preset CRUD operations with conflict prompts.

### 5. Recording Pipeline

- [x] Implement placeholder recording worker that writes silent WAV files for MVP wiring.
- [x] Build recording worker using `sounddevice` capturing PCM frames into a WAV file with graceful fallback handling.
- [ ] Support highest available quality by default (e.g., 48 kHz / 24-bit) with ability to downsample.
- [ ] On stop, open metadata dialog (`QDialog`) to capture Title/Artist/Album/Genre/Comments, commit via `mutagen`.
- [ ] Save output to user-configured directory; allow open-in-folder action.

### 6. Platform Considerations

- [ ] Windows: verify loopback capture and device enumeration, test exclusive/shared modes.
- [ ] Linux: support PulseAudio via `pulsectl`; fallback to ALSA/pipewire instructions if modules missing.
- [ ] Document required system packages and permissions.

### 7. Testing & QA

- [x] Unit tests for config handling, preset serialization, device service abstraction (mock backends).
- [ ] Integration smoke tests for recording pipeline (mock audio input, ensure file produced with metadata).
- [ ] Manual QA checklist for latency, clipping, and UI responsiveness.

### 8. Documentation & UX

- [ ] Update `docs/plugin-concepts.md` with implementation linkage and commands to install optional deps.
- [ ] Extend README with AudioTools summary and usage instructions.
- [ ] Provide troubleshooting tips for missing permissions or unsupported hardware.

## Milestones

1. **Scaffold & Device Discovery** – core service, config defaults, basic UI stub.
2. **Recording MVP** – capture audio to WAV with metadata entry, no EQ.
3. **Equalizer Integration** – full per-device EQ with presets and real-time feedback.
4. **Polish & Cross-Platform** – refine UX, add notifications, finalize docs/tests.
