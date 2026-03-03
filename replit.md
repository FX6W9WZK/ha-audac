# ha-audac-mtx

HACS Dashboard integration for Home Assistant to control Audac MTX audio matrices (MTX48/MTX88).

## Architecture

### Backend (Custom Component)
- `custom_components/audac_mtx/` — HA integration that communicates with MTX via TCP/IP (port 5001)
- `mtx_client.py` — Async TCP client with auto-reconnect, implementing the full MTX command protocol
- `coordinator.py` — HA DataUpdateCoordinator for polling zone states (10s interval)
- `media_player.py` — MediaPlayer entities per zone (volume, mute, source/routing, bass, treble)
- `config_flow.py` — UI-based setup flow (host, port, zone count) + Options flow for zone/source naming
- `translations/` — EN and DE translations for config and options flows

### Configuration
- **Initial Setup (Config Flow):** IP address, port (default 5001), number of zones (1-8), device name
- **Options Flow:** Custom zone names (per zone) and source/input names (per input 0-8)
- **Card Editor:** Title, theme, bass/treble toggle, source toggle, per-zone entity + display name

### Frontend (Lovelace Card)
- `src/audac-mtx-card.js` — Custom Lovelace card (Web Component), Bubble Card-inspired design
- `dist/audac-mtx-card.js` — Production build copy
- Card features: volume sliders, mute toggle, source selection grid, bass/treble display, dark/light theme
- Card editor with German labels, zone management (entity + name pairs)

### Preview Server
- `server.js` — Simple Node.js HTTP server for card preview with mock data
- `preview/index.html` — Preview page with mock HA states

## MTX Protocol
- TCP/IP on port 5001, command format: `#|X001|source|command|args|U|\r\n`
- Supports: volume (SV), routing/source (SR), bass (SB), treble (ST), mute (SM), zone info (GZI)
- Checksum always set to `U` (universal accept)

## Tech Stack
- Backend: Python (Home Assistant custom component)
- Frontend: Vanilla JS Web Component
- Preview: Node.js HTTP server (port 5000)
