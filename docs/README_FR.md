## g711xz - stockage sans perte des enregistrements d'appels G.711

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Tout appel qui traverse un réseau téléphonique en PCMU ou PCMA est déjà compressé : chaque échantillon de 16 bits ne prend qu'une valeur parmi 256 au plus. Stockez-le en WAV, et un octet sur deux est redondant. Stockez-le en MP3 ou en Opus, et le codec réécrit discrètement le son, d'une façon qu'une oreille humaine perçoit à peine et qu'un logiciel de reconnaissance vocale perçoit bien.

g711xz conserve l'appel exactement tel qu'il est arrivé. Il retransforme les échantillons en codes G.711 de 8 bits, les compresse avec xz et restitue le PCM d'origine au bit près. Les sonneries et les silences ne pèsent presque rien ; une conversation prend plus de place qu'en Opus. C'est un outil en ligne de commande et une bibliothèque Python pour Linux, macOS et Windows, avec une extension Rust dans les wheels publiés.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | **[Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md)** | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Prérequis

- **Python 3.9 ou supérieur**
- **Linux, macOS, Windows** : aucune exigence propre à la plateforme
- **Dépendances** : aucune, la bibliothèque standard suffit
- **Optionnel** : NumPy ou l'extension Rust, utilisés comme accélérateurs s'ils sont présents

### Format de fichier

Un fichier correspond à un appel enregistré : le canal gauche est l'appelant, le canal droit est l'appelé.

- ✅ Sans perte : le décodage restitue le PCM 16 bits de l'enregistreur, au bit près
- ✅ mu-law (PCMU) et A-law (PCMA)
- ✅ Environ un quart plus petit que xz sur le PCM brut
- ✅ Un seul flux xz standard, lisible avec `xz` seul
- ❌ Audio qui n'est pas du G.711 pur : refusé plutôt qu'arrondi
- ❌ Métadonnées : le fichier contient l'audio et rien d'autre

### Comparaison

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| Se décode vers l'original | oui | oui | oui | parole seulement | non | non |
| Mots identiques à la transcription d'origine, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| Appels à la transcription identique mot pour mot, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| Taille moyenne, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 minutes, MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| Charge CPU pour encoder, % d'Opus | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW est le flux mu-law brut, 8 kHz, stéréo. XZ est `xz -6` sur ces octets, OPUS est `opusenc --bitrate 32 --speech`, MP3 est `lame -b 32`. Les lignes de transcription comparent une transcription Whisper de chaque format avec la transcription du son d'origine.

- **xz seul est aussi sans perte, mais plus gros.** Il prend les octets comme ils viennent, g711xz range d'abord chaque côté de l'appel séparément : xz est environ 14 % plus gros et demande deux fois plus de CPU.
- **G711XZ VOX est le mode VOX en bêta** (`g711xz encode in.wav --vox`), désactivé par défaut. La parole est conservée bit pour bit et les longues plages de bruit de ligne régulier sont remplacées : le fichier est plus petit mais n'est plus une copie exacte. Tout lecteur 0.0.3 l'ouvre comme un fichier sans perte, et `g711xz info` indique le mode. Voir [VOX Mode (Beta)](FEATURES.md#vox-mode-beta).
- **La reconnaissance vocale n'est pas en cause.** Le même son transcrit deux fois concorde sur 99,98 % des mots et sur 99,8 % des appels : les écarts des colonnes Opus et MP3 viennent des codecs.
- **Pourquoi une conversation est plus grosse qu'en Opus et en MP3.** Ces codecs visent un débit et jettent ce qui ne rentre pas. g711xz garde chaque échantillon, et dans la parole les bits de poids faible de chaque code G.711 portent du bruit de ligne et des détails fins qu'aucun compresseur sans perte ne peut réduire. Les sonneries et les silences font l'inverse : ils ne pèsent presque rien, si bien que sur de nombreux appels g711xz reste proche d'Opus et bien en dessous du MP3.

### Installation

```bash
pip3 install g711xz
```

Ou depuis GitHub (cela compile l'extension Rust et demande une toolchain Rust et un compilateur C) :

```bash
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Utilisation

```bash
# Afficher l'en-tête, la durée et le débit d'un fichier
g711xz info rec.g711.xz

# Décoder vers un WAV stéréo sans perte (écrit rec.wav)
g711xz decode rec.g711.xz

# Décoder vers un fichier choisi
g711xz decode rec.g711.xz out.wav

# Encoder un WAV 2 canaux, 16 bits, 8000 Hz (écrit rec.g711.xz)
g711xz encode rec.wav

# Convertir vers l'autre loi, avec perte (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Bêta : écrire un fichier VOX plus petit, qui n'est pas une copie exacte (écrit rec.vox.g711.xz)
g711xz encode rec.wav --vox

# Un fichier VOX se lit comme n'importe quel autre ; info et la ligne de résultat de decode indiquent le mode
g711xz decode rec.vox.g711.xz

# Afficher l'aide
g711xz --help
```

Exemple de sortie de `g711xz info` :

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

# Décoder : law vaut b"u" ou b"a", pcm est du stéréo s16le entrelacé à 8000 Hz
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Encoder : renvoie les octets d'un fichier .g711.xz
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# Fichier VOX bêta : désactivé par défaut à l'écriture, lu comme n'importe quel autre fichier
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# Besoin de l'enregistrement exact ? Vérifier le mode
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

L'encodage lève `g711xz.RefusedError` lorsque le PCM n'est pas du G.711 pur, et la lecture lève `g711xz.FormatError` pour un fichier endommagé. Un fichier VOX n'est pas une erreur : `g711xz.read_mode` le distingue d'un fichier sans perte.

### Codes de sortie

| Code | Signification |
|------|---------|
| 0    | Succès. |
| 2    | Entrée invalide : fichier endommagé ou étranger, WAV au mauvais format, fichier introuvable, mauvais arguments CLI. |
| 3    | Encodage refusé : le PCM n'est pas du G.711 pur, un fichier sans perte ne peut donc pas être créé. |

### Commandes

- `info FILE [FILE ...]` - Afficher l'en-tête, la durée et le débit
- `decode FILE.g711.xz [OUT.wav]` - Décoder vers un WAV stéréo sans perte
- `encode FILE.wav [OUT.g711.xz] [--vox]` - Encoder un WAV 2 canaux, 16 bits, 8000 Hz
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - Convertir vers l'autre loi (avec perte)
- `--vox` - Bêta, uniquement avec `encode` : écrire un fichier VOX. `info`, `decode` et `transcode` lisent les deux modes et indiquent le mode
- `-h, --help` - Afficher l'aide

### Fonctionnalités

- **Aller-retour sans perte** pour les enregistrements mu-law et A-law
- **Encodeur strict** : refuse l'audio qui n'est pas du G.711 pur au lieu de le stocker avec perte
- **Lecteur strict** : rejette les fichiers endommagés, tronqués ou trop volumineux
- **Décodeur en flux** qui ne construit jamais tout le PCM en mémoire
- **Conversion entre lois** (de mu-law vers A-law et inversement)
- **Accélérateurs optionnels** : NumPy et une extension Rust, avec un repli en Python pur
- **Multiplateforme** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Guide complet des commandes, de l'API Python, des règles de validation, des messages d'erreur et des exemples.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Spécification de la structure de `.g711.xz` avec un vecteur de test, suffisante pour écrire un lecteur ou un encodeur indépendant.

### Outils de développement

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Recompiler l'extension Rust sur place (nécessite une toolchain Rust, un compilateur C et un virtualenv actif)
maturin develop --release
```

### Tests

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# La CI envoie automatiquement coverage.xml à Codecov

# Avec la bibliothèque standard uniquement
python3 -m unittest -v test_g711xz
```

### Licence

MIT License
