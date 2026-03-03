# Audac MTX

HACS Integration for Home Assistant to control Audac MTX audio matrices (MTX48/MTX88).
Standalone integration with direct TCP communication to the MTX device, including a Bubble Card-inspired Lovelace card.

## Architecture

### Backend (Custom Component)
- `custom_components/audac_mtx/` — HA integration
- `mtx_client.py` — Async TCP client with auto-reconnect (port 5001)
- `coordinator.py` — DataUpdateCoordinator, 10s polling interval
- `media_player.py` — MediaPlayer entities per zone (core: volume, mute, source, bass, treble)
- `select.py` — Select entities for source selection per zone
- `number.py` — Number entities for volume control per zone (0-100%)
- `switch.py` — Switch entities for mute toggle per zone
- `sensor.py` — Sensor entities showing active source per zone (read-only)
- `config_flow.py` — Setup flow (host, port, model, name) + Options flow for zone/source naming and visibility
- `services.yaml` — Custom services (set_bass, set_treble) under media_player domain
- `translations/` — EN and DE translations

### Entity Structure per Zone
| Entity | Domain | Role |
|--------|--------|------|
| media_player | `media_player` | Core zone entity (volume, mute, source, bass/treble) |
| select | `select` | Source selection (writable dropdown) |
| number | `number` | Volume 0-100% (slider) |
| switch | `switch` | Mute on/off |
| sensor | `sensor` | Active source (read-only display) |

### Frontend (Lovelace Card)
- `custom_components/audac_mtx/www/audac-mtx-card.js` — Web Component card
- 5 card types: `audac-mtx-card`, `audac-mtx-volume-card`, `audac-mtx-source-card`, `audac-mtx-bass-card`, `audac-mtx-treble-card`
- `audac-mtx-more-info` — Custom more-info dialog override for audac_mtx entities
- Auto-discovers media_player.audac_mtx_* entities
- Card editor with German labels

### HACS Structure (GitHub)
```
custom_components/audac_mtx/
  __init__.py, config_flow.py, const.py, coordinator.py,
  manifest.json, media_player.py, select.py, number.py,
  switch.py, sensor.py, mtx_client.py, services.yaml,
  strings.json, translations/{de,en}.json,
  www/audac-mtx-card.js
hacs.json
README.md
LICENSE
```

### Development (Replit only, gitignored)
- `server.js` — Node.js preview server (port 5000)
- `preview/index.html` — Mock HA states for card testing

### MTX Protocol
- TCP port 5001, format: `#|X001|web|CMD|ARG|U|\r\n`
- Volume: attenuation 0-70 (0=max, 70=min), card converts to 0-100%
- Routing: 0=Off, 1-8=Inputs
- Bass/Treble: 0-14 mapped to -14dB to +14dB

### Config Flow
- VERSION = 2 with async_migrate_entry for v1→v2 migration
- Model dropdown (MTX48=4 zones, MTX88=8 zones)
- Options: zone names, zone visibility, source names, source visibility

## Tech Stack
- Backend: Python (HA custom component)
- Frontend: Vanilla JS Web Component
- Preview: Node.js HTTP server (port 5000)
