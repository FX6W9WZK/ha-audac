# Audac MTX

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

Home Assistant Integration zur Steuerung von **Audac MTX** Audio-Matrizen (MTX48 / MTX88).

Kommuniziert direkt per TCP mit dem MTX-Gerät und liefert eine Bubble Card-inspirierte Lovelace Card mit.

---

## Features

- **Direkte TCP-Verbindung** – Kommuniziert direkt mit dem Audac MTX (Port 5001)
- **Media Player Entities** – Jede Zone wird als eigener Media Player dargestellt
- **Zonensteuerung** – Lautstärke, Mute, Quellenauswahl pro Zone
- **Bass & Höhen** – Anzeige der aktuellen Klangregelung (dB)
- **Quellenauswahl** – Übersichtliches Grid mit allen verfügbaren Eingängen
- **Automatische Erkennung** – Die Card findet alle MTX-Zonen automatisch
- **Benutzerdefinierte Namen** – Zonen und Quellen individuell benennen (über Optionen)
- **Dark / Light Mode** – Automatisch oder manuell wählbar
- **Bubble Card Design** – Abgerundete Ecken, sanfte Gradienten, flüssige Animationen
- **Card Editor** – Visuelle Konfiguration direkt im Lovelace-Editor

---

## Voraussetzungen

- Home Assistant 2023.9.0 oder neuer
- [HACS](https://hacs.xyz/) (empfohlen)
- Audac MTX48 oder MTX88, erreichbar im Netzwerk (TCP Port 5001)

---

## Installation

### Über HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu **Integrationen** → drei Punkte → **Benutzerdefinierte Repositories**
3. Füge `https://github.com/tuldener/Audac-Mtx-Control` hinzu, Kategorie **Integration**
4. Suche nach **Audac MTX** und installiere es
5. Starte Home Assistant neu
6. Gehe zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → **Audac MTX**

### Manuell

1. Kopiere den Ordner `custom_components/audac_mtx/` nach `config/custom_components/audac_mtx/`
2. Starte Home Assistant neu
3. Gehe zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → **Audac MTX**

---

## Einrichtung

### Integration konfigurieren

Beim Hinzufügen der Integration werden folgende Daten abgefragt:

| Feld | Beschreibung | Standard |
|------|-------------|----------|
| Host / IP-Adresse | IP des MTX-Geräts | – |
| Port | TCP-Port | `5001` |
| Anzahl der Zonen | 1–8 | `8` |
| Gerätename | Anzeigename | `Audac MTX` |

### Zonen- und Quellennamen anpassen

Über **Einstellungen** → **Geräte & Dienste** → **Audac MTX** → **Konfigurieren** können individuelle Namen vergeben werden:

- Zonennamen (z.B. "Empfangsbereich", "Konferenzraum", "Terrasse")
- Quellennamen (z.B. "Spotify", "Radio", "Mikrofon Bühne")

---

## Lovelace Card

Die Card wird automatisch als Lovelace-Ressource registriert. Falls nicht, manuell hinzufügen:

```yaml
resources:
  - url: /audac_mtx/audac-mtx-card.js
    type: module
```

### Einfach (Automatische Erkennung)

```yaml
type: custom:audac-mtx-card
title: Audac MTX
```

### Manuell (Zonen einzeln konfigurieren)

```yaml
type: custom:audac-mtx-card
title: Audio Steuerung
zones:
  - entity: media_player.audac_mtx_zone_1
    name: Empfangsbereich
  - entity: media_player.audac_mtx_zone_2
    name: Konferenzraum
  - entity: media_player.audac_mtx_zone_3
    name: Restaurant
show_bass_treble: true
show_source: true
theme: auto
```

### Card-Optionen

| Option | Beschreibung | Standard |
|--------|-------------|----------|
| `title` | Titel der Karte | `Audac MTX` |
| `zones` | Liste der Zonen (leer = Auto-Erkennung) | `[]` |
| `show_source` | Quellenauswahl anzeigen | `true` |
| `show_bass_treble` | Bass/Höhen anzeigen | `true` |
| `theme` | Design: `auto`, `dark`, `light` | `auto` |

### Zone-Konfiguration

| Option | Beschreibung |
|--------|-------------|
| `entity` | Entity-ID des Media Players (z.B. `media_player.audac_mtx_zone_1`) |
| `name` | Anzeigename (optional, sonst wird `friendly_name` verwendet) |
| `icon` | MDI-Icon (optional, Standard: `mdi:speaker`) |

---

## Entities

Pro Zone wird ein `media_player` Entity erstellt:

| Attribut | Beschreibung |
|----------|-------------|
| `volume_level` | Lautstärke (0.0 – 1.0) |
| `is_volume_muted` | Stummschaltung |
| `source` | Aktive Quelle |
| `source_list` | Verfügbare Quellen |
| `bass` | Bass-Einstellung (dB) |
| `treble` | Höhen-Einstellung (dB) |
| `volume_db` | Lautstärke in dB |
| `routing` | Aktive Routing-ID |

---

## MTX-Protokoll

| Befehl | Funktion |
|--------|---------|
| `GZI0X` | Zone-Info abrufen (Volume, Routing, Mute, Bass, Treble) |
| `SVX` | Lautstärke setzen (0=max, 70=min) |
| `SR X` | Routing/Quelle setzen |
| `SM0X` | Mute setzen (0/1) |
| `SB0X` | Bass setzen (0-14) |
| `ST0X` | Treble setzen (0-14) |

Protokollformat: `#|X001|web|CMD|ARG|U|\r\n`

---

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
