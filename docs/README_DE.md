## g711xz - verlustfreie Speicherung von G.711-Anrufaufzeichnungen

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Jedes Gespräch, das als PCMU oder PCMA durch ein Telefonnetz läuft, ist bereits komprimiert: Jedes 16-Bit-Sample hat höchstens 256 mögliche Werte. Als WAV gespeichert, ist jedes zweite Byte überflüssig. Als MP3 oder Opus gespeichert, schreibt der Codec den Ton stillschweigend um, und zwar so, dass ein Mensch es kaum hört, eine Spracherkennung aber sehr wohl.

g711xz bewahrt das Gespräch genau so, wie es angekommen ist. Es verwandelt die Samples zurück in ihre 8-Bit-G.711-Codes, packt sie mit xz und liefert das ursprüngliche PCM Bit für Bit zurück. Freizeichen und Stille schrumpfen fast auf nichts; ein Gespräch braucht mehr Platz als Opus. Es ist ein Kommandozeilenwerkzeug und eine Python-Bibliothek für Linux, macOS und Windows, mit einer Rust-Erweiterung in den veröffentlichten Wheels.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | **[Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md)** | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Anforderungen

- **Python 3.9 oder höher**
- **Linux, macOS, Windows**: keine plattformspezifischen Anforderungen
- **Abhängigkeiten**: keine, die Standardbibliothek genügt
- **Optional**: NumPy oder die Rust-Erweiterung, die als Beschleuniger genutzt werden, wenn sie vorhanden sind

### Dateiformat

Eine Datei ist ein aufgezeichnetes Gespräch: Der linke Kanal ist der Anrufer, der rechte Kanal der Angerufene.

- ✅ Verlustfrei: Die Dekodierung liefert das 16-Bit-PCM des Rekorders Bit für Bit zurück
- ✅ mu-law (PCMU) und A-law (PCMA)
- ✅ Etwa ein Viertel kleiner als xz auf dem rohen PCM
- ✅ Ein einzelner Standard-xz-Stream, allein mit `xz` lesbar
- ❌ Audio, das kein reines G.711 ist: wird abgelehnt statt gerundet
- ❌ Metadaten: Die Datei enthält das Audio und sonst nichts

### Vergleich

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| Dekodiert zurück zum Original | ja | ja | ja | nur Sprache | nein | nein |
| Wörter wie im Original-Transkript, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| Anrufe mit Wort für Wort gleichem Transkript, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| Mittlere Größe, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 Minuten, MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| CPU-Last beim Kodieren, % von Opus | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW ist der rohe mu-law-Stream, 8 kHz, stereo. XZ ist `xz -6` über diese Bytes, OPUS ist `opusenc --bitrate 32 --speech`, MP3 ist `lame -b 32`. Die Transkript-Zeilen vergleichen ein Whisper-Transkript jedes Formats mit dem Transkript des Originaltons.

- **xz allein ist auch verlustfrei, nur größer.** Es nimmt die Bytes, wie sie kommen, g711xz legt zuerst jede Seite des Anrufs für sich ab: xz wird etwa 14 % größer und braucht doppelt so viel CPU.
- **G711XZ VOX ist der VOX-Modus in der Beta** (`g711xz encode in.wav --vox`), standardmäßig aus. Sprache bleibt Bit für Bit erhalten, lange Strecken gleichmäßigen Leitungsrauschens werden ersetzt; die Datei ist dadurch kleiner, aber keine exakte Kopie mehr. Jeder Leser ab 0.0.3 öffnet sie wie eine verlustfreie Datei, und `g711xz info` zeigt den Modus. Siehe [VOX Mode (Beta)](FEATURES.md#vox-mode-beta).
- **Die Spracherkennung ist nicht schuld.** Derselbe Ton, zweimal transkribiert, stimmt in 99,98 % der Wörter und 99,8 % der Anrufe überein; die Abweichungen in den Spalten Opus und MP3 kommen also von den Codecs.
- **Warum ein Gespräch größer als Opus und MP3 ist.** Diese Codecs arbeiten auf eine Bitrate hin und werfen weg, was nicht hineinpasst. g711xz behält jedes Sample, und in Sprache tragen die unteren Bits jedes G.711-Codes Leitungsrauschen und feine Details, die kein verlustfreier Kompressor verkleinern kann. Freizeichen und Stille verhalten sich umgekehrt: Sie schrumpfen fast auf nichts, deshalb liegt g711xz über viele Anrufe nahe bei Opus und deutlich unter MP3.

### Installation

```bash
pip3 install g711xz
```

Oder von GitHub (dabei wird die Rust-Erweiterung gebaut, nötig sind eine Rust-Toolchain und ein C-Compiler):

```bash
sudo apt install git curl build-essential python3-pip
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Verwendung

```bash
# Header, Dauer und Bitrate einer Datei anzeigen
g711xz info rec.g711.xz

# In ein verlustfreies Stereo-WAV dekodieren (schreibt rec.wav)
g711xz decode rec.g711.xz

# In eine gewählte Datei dekodieren
g711xz decode rec.g711.xz out.wav

# Ein WAV mit 2 Kanälen, 16 Bit und 8000 Hz kodieren (schreibt rec.g711.xz)
g711xz encode rec.wav

# In die andere Kennlinie umwandeln, verlustbehaftet (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Beta: eine kleinere VOX-Datei schreiben, keine exakte Kopie (schreibt rec.vox.g711.xz)
g711xz encode rec.wav --vox

# Eine VOX-Datei wird wie jede andere gelesen; info und die Ergebniszeile von decode zeigen den Modus
g711xz decode rec.vox.g711.xz

# Hilfe anzeigen
g711xz --help
```

Beispielausgabe von `g711xz info`:

```
rec.g711.xz:
  format    CRG7 version 1
  mode      lossless
  law       mu-law (PCMU)
  channels  2 (left caller, right callee)
  rate      8000 Hz
  frames    480000
  duration  60.000 s
  size      108316 bytes (14.4 kbit/s)
```

### Python-API

```python
import g711xz

# Dekodieren: law ist b"u" oder b"a", pcm ist verschachteltes s16le-Stereo mit 8000 Hz
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Kodieren: gibt die Bytes einer .g711.xz-Datei zurück
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# Beta-VOX-Datei: beim Schreiben standardmäßig aus, gelesen wird sie wie jede andere Datei
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# Wird die exakte Aufzeichnung gebraucht? Den Modus prüfen
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

Das Kodieren löst `g711xz.RefusedError` aus, wenn das PCM kein reines G.711 ist, und das Lesen löst bei einer beschädigten Datei `g711xz.FormatError` aus. Eine VOX-Datei ist kein Fehler: `g711xz.read_mode` unterscheidet sie von einer verlustfreien.

### Exit-Codes

| Code | Bedeutung |
|------|---------|
| 0    | Erfolg. |
| 2    | Fehlerhafte Eingabe: beschädigte oder fremde Datei, WAV im falschen Format, fehlende Datei, falsche CLI-Argumente. |
| 3    | Kodierung abgelehnt: Das PCM ist kein reines G.711, eine verlustfreie Datei lässt sich daher nicht erzeugen. |

### Befehle

- `info FILE [FILE ...]` - Header, Dauer und Bitrate anzeigen
- `decode FILE.g711.xz [OUT.wav]` - In ein verlustfreies Stereo-WAV dekodieren
- `encode FILE.wav [OUT.g711.xz] [--vox]` - Ein WAV mit 2 Kanälen, 16 Bit und 8000 Hz kodieren
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - In die andere Kennlinie umwandeln (verlustbehaftet)
- `--vox` - Beta, nur für `encode`: eine VOX-Datei schreiben. `info`, `decode` und `transcode` lesen beide Modi und nennen den Modus
- `-h, --help` - Hilfe anzeigen

### Funktionen

- **Verlustfreier Hin- und Rückweg** für mu-law- und A-law-Aufzeichnungen
- **Strenger Encoder**: lehnt Audio ab, das kein reines G.711 ist, statt es verlustbehaftet zu speichern
- **Strenger Leser**: weist beschädigte, abgeschnittene und übergroße Dateien zurück
- **Streaming-Decoder**, der nie das gesamte PCM im Speicher aufbaut
- **Umwandlung zwischen den Kennlinien** (mu-law nach A-law und zurück)
- **Optionale Beschleuniger**: NumPy und eine Rust-Erweiterung, mit reinem Python als Rückfallebene
- **Plattformübergreifend** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Ausführliche Anleitung zu Befehlen, Python-API, Validierungsregeln, Fehlermeldungen und Beispielen.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Spezifikation des `.g711.xz`-Aufbaus mit einem Testvektor, ausreichend, um einen unabhängigen Leser oder Schreiber zu implementieren.

### Entwicklungstools

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Rust-Erweiterung vor Ort neu bauen (benötigt eine Rust-Toolchain, einen C-Compiler und ein aktives virtualenv)
maturin develop --release
```

### Tests

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# Die CI lädt coverage.xml automatisch zu Codecov hoch

# Nur mit der Standardbibliothek
python3 -m unittest -v test_g711xz
```

### Lizenz

MIT License
