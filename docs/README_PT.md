## g711xz - armazenamento sem perdas de gravações de chamadas G.711

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Toda chamada que atravessa uma rede telefônica como PCMU ou PCMA já chega comprimida: cada amostra de 16 bits é um de, no máximo, 256 valores. Salve como WAV e metade dos bytes é redundante. Salve como MP3 ou Opus e o codec reescreve o áudio em silêncio, com mudanças que uma pessoa mal percebe e um reconhecedor de fala percebe.

g711xz guarda a chamada exatamente como ela chegou. Converte as amostras de volta em seus códigos G.711 de 8 bits, compacta com xz e devolve o PCM original bit a bit. Toques e silêncio quase desaparecem; uma conversa ocupa mais que o Opus. É uma ferramenta de linha de comando e uma biblioteca Python para Linux, macOS e Windows, com uma extensão em Rust nos wheels publicados.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | **[Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md)** | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Requisitos

- **Python 3.9 ou superior**
- **Linux, macOS, Windows**: sem requisitos específicos da plataforma
- **Dependências**: nenhuma, a biblioteca padrão é suficiente
- **Opcional**: NumPy ou a extensão em Rust, usados como aceleradores quando presentes

### Formato de arquivo

Um arquivo é uma chamada gravada: o canal esquerdo é quem liga e o canal direito é quem recebe a chamada.

- ✅ Sem perdas: a decodificação devolve o PCM de 16 bits do gravador, bit a bit
- ✅ mu-law (PCMU) e A-law (PCMA)
- ✅ Cerca de um quarto menor que o xz sobre o PCM
- ✅ Um único fluxo xz padrão, legível apenas com `xz`
- ❌ Áudio que não é G.711 puro: é recusado em vez de arredondado
- ❌ Metadados: o arquivo contém o áudio e nada mais

### Comparação

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| Decodifica de volta ao original | sim | sim | sim | só a fala | não | não |
| Palavras iguais às da transcrição original, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| Chamadas com transcrição idêntica palavra por palavra, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| Tamanho médio, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 minutos, MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| Uso de CPU para codificar, % do Opus | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW é o fluxo mu-law bruto, estéreo a 8 kHz. XZ é `xz -6` sobre esses bytes, OPUS é `opusenc --bitrate 32 --speech`, MP3 é `lame -b 32`. As linhas de transcrição comparam a transcrição do Whisper de cada formato com a do áudio original.

- **O xz sozinho também é sem perdas, só que maior.** Ele pega os bytes como chegam, e o g711xz antes dispõe cada lado da chamada separadamente: o xz fica cerca de 14% maior e gasta o dobro de CPU.
- **G711XZ VOX é o modo VOX em beta** (`g711xz encode in.wav --vox`), desligado por padrão. A fala é mantida bit a bit e os trechos longos de ruído de linha uniforme são substituídos, então o arquivo fica menor, mas deixa de ser uma cópia exata. Qualquer leitor 0.0.3 o abre como um arquivo sem perdas, e `g711xz info` mostra o modo. Veja [VOX Mode (Beta)](FEATURES.md#vox-mode-beta).
- **O reconhecedor não é o culpado.** O mesmo áudio transcrito duas vezes coincide em 99,98% das palavras e em 99,8% das chamadas, então as diferenças nas colunas de Opus e MP3 vêm dos codecs.
- **Por que uma conversa fica maior que Opus e MP3.** Eles trabalham com um bitrate definido e descartam o que não cabe. O g711xz guarda cada amostra, e na fala os bits baixos de cada código G.711 carregam ruído de linha e detalhes finos que nenhum compressor sem perdas consegue reduzir. Toques e silêncio funcionam ao contrário: quase desaparecem na compressão, então em muitas chamadas o g711xz fica perto do Opus e bem abaixo do MP3.

### Instalação

```bash
pip3 install g711xz
```

Ou a partir do GitHub (compila a extensão em Rust e requer um toolchain Rust e um compilador C):

```bash
sudo apt install git curl build-essential python3-pip
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Uso

```bash
# Mostrar o cabeçalho, a duração e o bitrate de um arquivo
g711xz info rec.g711.xz

# Decodificar para um WAV estéreo sem perdas (grava rec.wav)
g711xz decode rec.g711.xz

# Decodificar para um arquivo escolhido
g711xz decode rec.g711.xz out.wav

# Codificar um WAV de 2 canais, 16 bits e 8000 Hz (grava rec.g711.xz)
g711xz encode rec.wav

# Converter para a outra lei, com perdas (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Beta: gravar um arquivo VOX menor, que não é uma cópia exata (grava rec.vox.g711.xz)
g711xz encode rec.wav --vox

# Um arquivo VOX é lido como qualquer outro; info e a linha de resultado de decode mostram o modo
g711xz decode rec.vox.g711.xz

# Mostrar ajuda
g711xz --help
```

Exemplo de saída de `g711xz info`:

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

# Decodificar: law é b"u" ou b"a", pcm é estéreo s16le intercalado a 8000 Hz
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Codificar: retorna os bytes de um arquivo .g711.xz
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# Arquivo VOX beta: desligado por padrão na gravação, lido como qualquer outro arquivo
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# Precisa da gravação exata? Verifique o modo
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

A codificação lança `g711xz.RefusedError` quando o PCM não é G.711 puro, e a leitura lança `g711xz.FormatError` para um arquivo danificado. Um arquivo VOX não é um erro: `g711xz.read_mode` o distingue de um sem perdas.

### Códigos de saída

| Código | Significado |
|------|---------|
| 0    | Sucesso. |
| 2    | Entrada inválida: um arquivo danificado ou estranho, um WAV no formato errado, um arquivo inexistente, argumentos de CLI incorretos. |
| 3    | Codificação recusada: o PCM não é G.711 puro, portanto não é possível criar um arquivo sem perdas. |

### Comandos

- `info FILE [FILE ...]` - Mostrar o cabeçalho, a duração e o bitrate
- `decode FILE.g711.xz [OUT.wav]` - Decodificar para um WAV estéreo sem perdas
- `encode FILE.wav [OUT.g711.xz] [--vox]` - Codificar um WAV de 2 canais, 16 bits e 8000 Hz
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - Converter para a outra lei (com perdas)
- `--vox` - Beta, apenas com `encode`: gravar um arquivo VOX. `info`, `decode` e `transcode` leem os dois modos e informam o modo
- `-h, --help` - Mostrar ajuda

### Funcionalidades

- **Ida e volta sem perdas** para gravações mu-law e A-law
- **Codificador rigoroso**: recusa áudio que não é G.711 puro em vez de armazená-lo com perdas
- **Leitor rigoroso**: rejeita arquivos danificados, truncados ou grandes demais
- **Decodificador em fluxo** que nunca monta o PCM inteiro na memória
- **Conversão entre leis** (de mu-law para A-law e vice-versa)
- **Aceleradores opcionais**: NumPy e uma extensão em Rust, com alternativa em Python puro
- **Multiplataforma** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Guia completo dos comandos, da API Python, das regras de validação, das mensagens de erro e exemplos.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Especificação da estrutura de `.g711.xz` com um vetor de teste, suficiente para escrever um leitor ou gravador independente.

### Ferramentas de desenvolvimento

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Recompilar a extensão em Rust (requer um toolchain Rust, um compilador C e um virtualenv ativo)
maturin develop --release
```

### Testes

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# O CI envia automaticamente o coverage.xml para o Codecov

# Apenas com a biblioteca padrão
python3 -m unittest -v test_g711xz
```

### Licença

MIT License
