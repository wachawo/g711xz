## g711xz - verlustfreie Speicherung von G.711-Anrufaufzeichnungen

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Jedes Gespräch, das als PCMU oder PCMA durch ein Telefonnetz läuft, ist bereits komprimiert: Jedes 16-Bit-Sample hat höchstens 256 mögliche Werte. Als WAV gespeichert, ist jedes zweite Byte überflüssig. Als MP3 oder Opus gespeichert, schreibt der Codec den Ton stillschweigend um, und zwar so, dass ein Mensch es kaum hört, eine Spracherkennung aber sehr wohl.

g711xz bewahrt das Gespräch genau so, wie es angekommen ist. Es verwandelt die Samples zurück in ihre 8-Bit-G.711-Codes, packt sie mit xz und liefert das ursprüngliche PCM Bit für Bit zurück. Freizeichen und Stille schrumpfen fast auf nichts; ein Gespräch braucht mehr Platz als Opus. Es ist ein Kommandozeilenwerkzeug und eine Bibliothek in reinem Python für Linux, macOS und Windows.

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

| | PCM | xz | g711xz | Opus 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|
| Dekodiert zurück zum Original | ja | ja | ja | nein | nein |
| Wörter wie im Original-Transkript, % | 100 | 99.9 | 99.9 | 94.2 | 93.8 |
| Anrufe mit Wort für Wort gleichem Transkript, % | 100 | 99.8 | 99.8 | 67.3 | 60.5 |
| Mittlere Größe, kbit/s | 256 | 24.7 | 18.8 | 20.2 | 32.4 |
| Anruf von 5 Minuten, MB | 9.60 | 2.29 | 1.77 | 0.97 | 1.20 |
| CPU zum Kodieren, relativ zu Opus | 0 | 0.4 | 0.2 | 1 | 0.16 |

- **xz allein ist auch verlustfrei, nur größer.** Es komprimiert die 16-Bit-Samples, g711xz die 8-Bit-Codes, aus denen sie entstanden sind: xz wird etwa 30 % größer und braucht doppelt so viel CPU.
- **Die 0,1 % kommen von der Spracherkennung, nicht von der Datei.** Die verlustfreien Formate dekodieren genau zu den ursprünglichen Bytes; ein zweiter Durchlauf desselben Tons liefert nicht immer dieselben Wörter.
- **Warum ein Gespräch größer als Opus und MP3 ist.** Diese Codecs arbeiten auf eine Bitrate hin und werfen weg, was nicht hineinpasst. g711xz behält jedes Sample, und in Sprache tragen die unteren Bits jedes G.711-Codes Leitungsrauschen und feine Details, die kein verlustfreier Kompressor verkleinern kann. Freizeichen und Stille verhalten sich umgekehrt: Sie schrumpfen fast auf nichts, deshalb ist g711xz über viele Anrufe im Mittel kleiner.

### Installation

```bash
pip3 install g711xz
```

Oder von GitHub:

```bash
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

# Hilfe anzeigen
g711xz --help
```

Beispielausgabe von `g711xz info`:

```
rec.g711.xz:
  format    CRG7 version 1
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
```

Das Kodieren löst `g711xz.RefusedError` aus, wenn das PCM kein reines G.711 ist, und das Lesen löst bei einer beschädigten Datei `g711xz.FormatError` aus.

### Exit-Codes

| Code | Bedeutung |
|------|---------|
| 0    | Erfolg. |
| 2    | Fehlerhafte Eingabe: beschädigte oder fremde Datei, WAV im falschen Format, fehlende Datei, falsche CLI-Argumente. |
| 3    | Kodierung abgelehnt: Das PCM ist kein reines G.711, eine verlustfreie Datei lässt sich daher nicht erzeugen. |

### Befehle

- `info FILE [FILE ...]` - Header, Dauer und Bitrate anzeigen
- `decode FILE.g711.xz [OUT.wav]` - In ein verlustfreies Stereo-WAV dekodieren
- `encode FILE.wav [OUT.g711.xz]` - Ein WAV mit 2 Kanälen, 16 Bit und 8000 Hz kodieren
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - In die andere Kennlinie umwandeln (verlustbehaftet)
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

# Optionale Rust-Erweiterung (benötigt eine Rust-Toolchain und ein aktives virtualenv)
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
