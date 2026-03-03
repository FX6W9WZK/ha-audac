# Audac MTX

HACS Integration for Home Assistant to control Audac MTX audio matrices (MTX48/MTX88).
Standalone integration with direct TCP communication to the MTX device, including a Bubble Card-inspired Lovelace card.

## Architecture

### Backend (Custom Component)
- `custom_components/audac_mtx/` — HA integration
- `mtx_client.py` — Async TCP client with auto-reconnect (port 5001)
- `coordinator.py` — DataUpdateCoordinator, 10s polling interval
- `media_player.py` — MediaPlayer entities per zone (volume, mute, source, bass, treble)
- `config_flow.py` — Setup flow (host, port, zones, name) + Options flow for zone/source naming
- `translations/` — EN and DE translations

### Frontend (Lovelace Card)
- `custom_components/audac_mtx/www/audac-mtx-card.js` — Web Component card
- Auto-discovers media_player.audac_mtx_* entities
- Uses media_player services: volume_set, volume_mute, select_source
- Card editor with German labels

### HACS Structure (GitHub)
```
custom_components/audac_mtx/
  __init__.py, config_flow.py, const.py, coordinator.py,
  manifest.json, media_player.py, mtx_client.py, strings.json,
  translations/{de,en}.json, www/audac-mtx-card.js
hacs.json
README.md
LICENSE
```

### Development (Replit only, gitignored)
- `server.js` — Node.js preview server (port 5000)
- `preview/index.html` — Mock HA states for card testing
- `src/`, `dist/` — Development copies

### MTX Protocol
- TCP port 5001, format: `#|X001|web|CMD|ARG|U|\r\n`
- Volume: attenuation 0-70 (0=max, 70=min), card converts to 0-100%
- Routing: 0=Off, 1-8=Inputs
- Bass/Treble: 0-14 mapped to -14dB to +14dB

## Tech Stack
- Backend: Python (HA custom component)
- Frontend: Vanilla JS Web Component
- Preview: Node.js HTTP server (port 5000)
