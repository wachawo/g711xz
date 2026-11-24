## g711xz - almacenamiento sin pérdidas de grabaciones de llamadas G.711

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Cada llamada que cruza una red telefónica como PCMU o PCMA ya viene comprimida: cada muestra de 16 bits es uno de, como mucho, 256 valores. Guárdala como WAV y uno de cada dos bytes sobra. Guárdala como MP3 u Opus y el códec reescribe el audio en silencio, con cambios que una persona apenas oye y un reconocedor de voz sí.

g711xz guarda la llamada tal como llegó. Convierte las muestras de nuevo en sus códigos G.711 de 8 bits, las empaqueta con xz y devuelve el PCM original bit a bit. Los tonos y el silencio se reducen casi a nada; una conversación ocupa más que Opus. Es una herramienta de línea de comandos y una biblioteca de Python para Linux, macOS y Windows, con una extensión en Rust en los wheels publicados.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | **[Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md)** | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Requisitos

- **Python 3.9 o superior**
- **Linux, macOS, Windows**: sin requisitos específicos de la plataforma
- **Dependencias**: ninguna, basta con la biblioteca estándar
- **Opcional**: NumPy o la extensión en Rust, que se usan como aceleradores si están presentes

### Formato de archivo

Un archivo es una llamada grabada: el canal izquierdo es quien llama y el canal derecho es quien recibe la llamada.

- ✅ Sin pérdidas: la decodificación devuelve el PCM de 16 bits de la grabadora, bit a bit
- ✅ mu-law (PCMU) y A-law (PCMA)
- ✅ Alrededor de un cuarto más pequeño que xz sobre el PCM
- ✅ Un único flujo xz estándar, legible solo con `xz`
- ❌ Audio que no es G.711 puro: se rechaza en lugar de redondearse
- ❌ Metadatos: el archivo contiene el audio y nada más

### Comparación

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| Se decodifica al original | sí | sí | sí | solo la voz | no | no |
| Palabras que coinciden con la transcripción original, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| Llamadas con transcripción idéntica palabra por palabra, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| Tamaño medio, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 minutos, MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| Uso de CPU para codificar, % de Opus | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW es el flujo mu-law en bruto, 8 kHz, estéreo. XZ es `xz -6` sobre esos bytes, OPUS es `opusenc --bitrate 32 --speech`, MP3 es `lame -b 32`. Las filas de transcripción comparan una transcripción de Whisper de cada formato con la transcripción del audio original.

- **xz solo también es sin pérdidas, pero más grande.** Toma los bytes tal como vienen, y g711xz coloca primero cada lado de la llamada por separado: xz ocupa alrededor de un 14% más y gasta el doble de CPU.
- **G711XZ VOX es el modo VOX en beta** (`g711xz encode in.wav --vox`), desactivado por defecto. La voz se conserva bit a bit y los tramos largos de ruido de línea uniforme se sustituyen, así que el archivo es más pequeño pero ya no es una copia exacta. Cualquier lector 0.0.3 lo abre como un archivo sin pérdidas, y `g711xz info` muestra el modo. Véase [VOX Mode (Beta)](FEATURES.md#vox-mode-beta).
- **El reconocedor no tiene la culpa.** El mismo audio transcrito dos veces coincide en el 99,98% de las palabras y en el 99,8% de las llamadas, así que las diferencias en las columnas de Opus y MP3 vienen de los códecs.
- **Por qué una conversación ocupa más que Opus y MP3.** Ellos trabajan con un bitrate fijado y descartan lo que no cabe. g711xz conserva cada muestra, y en la voz los bits bajos de cada código G.711 llevan ruido de línea y detalles finos que ningún compresor sin pérdidas puede reducir. Los tonos y el silencio funcionan al revés: se comprimen casi a nada, así que en muchas llamadas g711xz queda cerca de Opus y muy por debajo de MP3.

### Instalación

```bash
pip3 install g711xz
```

O desde GitHub (compila la extensión en Rust y necesita un toolchain de Rust y un compilador de C):

```bash
sudo apt install git curl build-essential python3-pip
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Uso

```bash
# Mostrar el encabezado, la duración y el bitrate de un archivo
g711xz info rec.g711.xz

# Decodificar a un WAV estéreo sin pérdidas (escribe rec.wav)
g711xz decode rec.g711.xz

# Decodificar a un archivo elegido
g711xz decode rec.g711.xz out.wav

# Codificar un WAV de 2 canales, 16 bits y 8000 Hz (escribe rec.g711.xz)
g711xz encode rec.wav

# Convertir a la otra ley, con pérdidas (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Beta: escribir un archivo VOX más pequeño, que no es una copia exacta (escribe rec.vox.g711.xz)
g711xz encode rec.wav --vox

# Un archivo VOX se lee como cualquier otro; info y la línea de resultado de decode muestran el modo
g711xz decode rec.vox.g711.xz

# Mostrar ayuda
g711xz --help
```

Ejemplo de salida de `g711xz info`:

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

### API de Python

```python
import g711xz

# Decodificar: law es b"u" o b"a", pcm es estéreo s16le intercalado a 8000 Hz
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Codificar: devuelve los bytes de un archivo .g711.xz
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# Archivo VOX beta: desactivado por defecto al escribir, se lee como cualquier otro archivo
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# ¿Hace falta la grabación exacta? Comprobar el modo
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

La codificación lanza `g711xz.RefusedError` cuando el PCM no es G.711 puro, y la lectura lanza `g711xz.FormatError` ante un archivo dañado. Un archivo VOX no es un error: `g711xz.read_mode` lo distingue de uno sin pérdidas.

### Códigos de salida

| Código | Significado |
|------|---------|
| 0    | Éxito. |
| 2    | Entrada incorrecta: un archivo dañado o ajeno, un WAV con formato equivocado, un archivo inexistente, argumentos de CLI incorrectos. |
| 3    | Codificación rechazada: el PCM no es G.711 puro, por lo que no se puede crear un archivo sin pérdidas. |

### Comandos

- `info FILE [FILE ...]` - Mostrar el encabezado, la duración y el bitrate
- `decode FILE.g711.xz [OUT.wav]` - Decodificar a un WAV estéreo sin pérdidas
- `encode FILE.wav [OUT.g711.xz] [--vox]` - Codificar un WAV de 2 canales, 16 bits y 8000 Hz
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - Convertir a la otra ley (con pérdidas)
- `--vox` - Beta, solo con `encode`: escribir un archivo VOX. `info`, `decode` y `transcode` leen ambos modos e indican el modo
- `-h, --help` - Mostrar ayuda

### Características

- **Ida y vuelta sin pérdidas** para grabaciones mu-law y A-law
- **Codificador estricto**: rechaza el audio que no es G.711 puro en lugar de guardarlo con pérdidas
- **Lector estricto**: rechaza archivos dañados, truncados o demasiado grandes
- **Decodificador en flujo** que nunca construye todo el PCM en memoria
- **Conversión entre leyes** (de mu-law a A-law y viceversa)
- **Aceleradores opcionales**: NumPy y una extensión en Rust, con una alternativa en Python puro
- **Multiplataforma** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Guía completa de los comandos, la API de Python, las reglas de validación, los mensajes de error y ejemplos.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Especificación de la estructura de `.g711.xz` con un vector de prueba, suficiente para escribir un lector o un escritor independiente.

### Herramientas de desarrollo

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Recompilar la extensión en Rust (requiere un toolchain de Rust, un compilador de C y un virtualenv activo)
maturin develop --release
```

### Pruebas

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# CI sube automáticamente coverage.xml a Codecov

# Solo con la biblioteca estándar
python3 -m unittest -v test_g711xz
```

### Licencia

MIT License
