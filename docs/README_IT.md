## g711xz - archiviazione senza perdita di registrazioni di chiamate G.711

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Ogni chiamata che attraversa una rete telefonica come PCMU o PCMA è già compressa: ogni campione a 16 bit assume al massimo 256 valori. Salvala come WAV e un byte su due è superfluo. Salvala come MP3 o Opus e il codec riscrive l'audio in silenzio, con cambiamenti che una persona sente appena e un riconoscitore vocale invece nota.

g711xz conserva la chiamata esattamente com'è arrivata. Riporta i campioni ai loro codici G.711 a 8 bit, li comprime con xz e restituisce il PCM originale bit per bit. Squilli e silenzio si riducono quasi a nulla; una conversazione occupa più spazio di Opus. È uno strumento da riga di comando e una libreria Python per Linux, macOS e Windows, con un'estensione Rust nei wheel pubblicati.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | **[Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md)** | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Requisiti

- **Python 3.9 o superiore**
- **Linux, macOS, Windows**: nessun requisito specifico della piattaforma
- **Dipendenze**: nessuna, basta la libreria standard
- **Opzionale**: NumPy o l'estensione Rust, usati come acceleratori quando presenti

### Formato del file

Un file è una chiamata registrata: il canale sinistro è il chiamante, il canale destro è il chiamato.

- ✅ Senza perdita: la decodifica restituisce il PCM a 16 bit del registratore, bit per bit
- ✅ mu-law (PCMU) e A-law (PCMA)
- ✅ Circa un quarto più piccolo di xz sul PCM grezzo
- ✅ Un unico flusso xz standard, leggibile con il solo `xz`
- ❌ Audio che non è G.711 puro: viene rifiutato invece di essere arrotondato
- ❌ Metadati: il file contiene l'audio e nient'altro

### Confronto

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| Si decodifica nell'originale | sì | sì | sì | solo il parlato | no | no |
| Parole uguali alla trascrizione originale, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| Chiamate con trascrizione identica parola per parola, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| Dimensione media, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 minuti, MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| Uso di CPU per codificare, % di Opus | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW è il flusso mu-law grezzo, stereo a 8 kHz. XZ è `xz -6` su quei byte, OPUS è `opusenc --bitrate 32 --speech`, MP3 è `lame -b 32`. Le righe sulla trascrizione confrontano la trascrizione Whisper di ogni formato con quella dell'audio originale.

- **Anche xz da solo è senza perdita, solo più grande.** Prende i byte così come arrivano, mentre g711xz prima dispone separatamente ciascun lato della chiamata: xz risulta circa il 14% più grande e usa il doppio della CPU.
- **G711XZ VOX è la modalità VOX in beta** (`g711xz encode in.wav --vox`), disattivata per impostazione predefinita. Il parlato è conservato bit per bit e i lunghi tratti di rumore di linea uniforme vengono sostituiti: il file è più piccolo ma non è più una copia esatta. Qualsiasi lettore 0.0.3 lo apre come un file senza perdita, e `g711xz info` mostra la modalità. Vedi [VOX Mode (Beta)](FEATURES.md#vox-mode-beta).
- **Il riconoscitore non c'entra.** Lo stesso audio trascritto due volte coincide nel 99,98% delle parole e nel 99,8% delle chiamate, quindi le differenze nelle colonne Opus e MP3 vengono dai codec.
- **Perché una conversazione è più grande di Opus e MP3.** Questi codec lavorano su un bitrate e scartano ciò che non ci sta. g711xz conserva ogni campione, e nel parlato i bit bassi di ogni codice G.711 portano rumore di linea e dettagli fini che nessun compressore senza perdita può ridurre. Squilli e silenzio funzionano al contrario: si riducono quasi a nulla, quindi su molte chiamate g711xz resta vicino a Opus e ben sotto l'MP3.

### Installazione

```bash
pip3 install g711xz
```

Oppure da GitHub (compila l'estensione Rust e richiede una toolchain Rust e un compilatore C):

```bash
sudo apt install git curl build-essential python3-pip
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Utilizzo

```bash
# Mostrare l'intestazione, la durata e il bitrate di un file
g711xz info rec.g711.xz

# Decodificare in un WAV stereo senza perdita (scrive rec.wav)
g711xz decode rec.g711.xz

# Decodificare in un file a scelta
g711xz decode rec.g711.xz out.wav

# Codificare un WAV a 2 canali, 16 bit, 8000 Hz (scrive rec.g711.xz)
g711xz encode rec.wav

# Convertire nell'altra legge, con perdita (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Beta: scrivere un file VOX più piccolo, che non è una copia esatta (scrive rec.vox.g711.xz)
g711xz encode rec.wav --vox

# Un file VOX si legge come qualsiasi altro; info e la riga di risultato di decode mostrano la modalità
g711xz decode rec.vox.g711.xz

# Mostrare l'aiuto
g711xz --help
```

Esempio di output di `g711xz info`:

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

### API Python

```python
import g711xz

# Decodifica: law è b"u" o b"a", pcm è stereo s16le interlacciato a 8000 Hz
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Codifica: restituisce i byte di un file .g711.xz
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# File VOX beta: disattivato per impostazione predefinita in scrittura, si legge come qualsiasi altro file
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# Serve la registrazione esatta? Controllare la modalità
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

La codifica solleva `g711xz.RefusedError` quando il PCM non è G.711 puro, e la lettura solleva `g711xz.FormatError` per un file danneggiato. Un file VOX non è un errore: `g711xz.read_mode` lo distingue da uno senza perdita.

### Codici di uscita

| Codice | Significato |
|------|---------|
| 0    | Successo. |
| 2    | Input non valido: un file danneggiato o estraneo, un WAV nel formato sbagliato, un file mancante, argomenti CLI errati. |
| 3    | Codifica rifiutata: il PCM non è G.711 puro, quindi non si può creare un file senza perdita. |

### Comandi

- `info FILE [FILE ...]` - Mostrare l'intestazione, la durata e il bitrate
- `decode FILE.g711.xz [OUT.wav]` - Decodificare in un WAV stereo senza perdita
- `encode FILE.wav [OUT.g711.xz] [--vox]` - Codificare un WAV a 2 canali, 16 bit, 8000 Hz
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - Convertire nell'altra legge (con perdita)
- `--vox` - Beta, solo con `encode`: scrivere un file VOX. `info`, `decode` e `transcode` leggono entrambe le modalità e indicano la modalità
- `-h, --help` - Mostrare l'aiuto

### Funzionalità

- **Andata e ritorno senza perdita** per registrazioni mu-law e A-law
- **Codificatore rigoroso**: rifiuta l'audio che non è G.711 puro invece di salvarlo con perdita
- **Lettore rigoroso**: rifiuta file danneggiati, troncati o troppo grandi
- **Decodificatore in streaming** che non costruisce mai l'intero PCM in memoria
- **Conversione tra leggi** (da mu-law ad A-law e viceversa)
- **Acceleratori opzionali**: NumPy e un'estensione Rust, con ripiego in Python puro
- **Multipiattaforma** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Guida completa a comandi, API Python, regole di validazione, messaggi di errore ed esempi.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Specifica della struttura di `.g711.xz` con un vettore di test, sufficiente per scrivere un lettore o uno scrittore indipendente.

### Strumenti di sviluppo

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Ricompilare l'estensione Rust sul posto (richiede una toolchain Rust, un compilatore C e un virtualenv attivo)
maturin develop --release
```

### Test

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# La CI carica automaticamente coverage.xml su Codecov

# Solo con la libreria standard
python3 -m unittest -v test_g711xz
```

### Licenza

MIT License
