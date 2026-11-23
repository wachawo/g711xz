## g711xz - G.711 通話録音のロスレス保存

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

PCMU や PCMA として電話網を通る通話は、すでに圧縮されています。16 ビットの各サンプルが取りうる値は最大 256 個だけです。WAV で保存すると 1 バイトおきに冗長になります。MP3 や Opus で保存すると、コーデックが音声を黙って書き換えます。人の耳にはほとんど分からない変化ですが、音声認識には分かります。

g711xz は通話を届いたときのまま保存します。サンプルを 8 ビットの G.711 コードに戻して xz で圧縮し、元の PCM をビット単位で完全に復元します。呼び出し音や無音はほとんどゼロまで縮みますが、会話は Opus より大きくなります。Linux、macOS、Windows で動くコマンドラインツールであり Python ライブラリで、公開されている wheel には Rust 拡張が含まれます。

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | **[日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md)** | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### 要件

- **Python 3.9 以上**
- **Linux、macOS、Windows**: プラットフォーム固有の要件はありません
- **依存関係**: なし。標準ライブラリだけで動作します
- **オプション**: NumPy または Rust 拡張。存在する場合は高速化に使われます

### ファイル形式

1 つのファイルが 1 件の通話録音です。左チャンネルが発信者、右チャンネルが着信者です。

- ✅ ロスレス: デコードすると録音機の 16 ビット PCM がビット単位で完全に戻ります
- ✅ mu-law (PCMU) と A-law (PCMA)
- ✅ 生の PCM を xz で圧縮するより約 4 分の 1 小さい
- ✅ 標準の xz ストリーム 1 本で、`xz` だけで読み出せます
- ❌ 純粋な G.711 ではない音声: 丸めずに拒否します
- ❌ メタデータ: ファイルには音声だけが入っています

### 比較

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| 元の音声に戻せる | はい | はい | はい | 発話のみ | いいえ | いいえ |
| 元の文字起こしと一致した単語, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| 文字起こしが一語一句同じだった通話, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| 平均サイズ, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 分間、MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| エンコードの CPU 使用率、Opus 比 % | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW は 8 kHz ステレオの mu-law ストリームそのものです。XZ はそのバイト列に `xz -6` をかけたもの、OPUS は `opusenc --bitrate 32 --speech`、MP3 は `lame -b 32` です。文字起こしの行は、各形式の Whisper による文字起こしを元の音声の文字起こしと比べたものです。

- **xz 単体もロスレスですが、大きくなります。** xz はバイト列を来た順のまま扱い、g711xz は先に通話の各側を別々に並べ直します。xz は約 14% 大きく、CPU も 2 倍かかります。
- **G711XZ VOX はベータの VOX モードです** (`g711xz encode in.wav --vox`)。既定では無効です。発話はビット単位でそのまま保持し、一様な回線ノイズが長く続く区間は置き換えます。そのためファイルは小さくなりますが、完全な複製ではなくなります。0.0.3 のリーダーであればロスレスのファイルと同じように開け、`g711xz info` がモードを表示します。[VOX Mode (Beta)](FEATURES.md#vox-mode-beta) を参照してください。
- **音声認識のせいではありません。** 同じ音声を 2 回文字起こしすると、単語の 99.98%、通話の 99.8% が一致します。Opus と MP3 の列の差はコーデックによるものです。
- **会話が Opus や MP3 より大きくなる理由。** これらはビットレートに合わせてエンコードし、収まらない部分は捨てます。g711xz はすべてのサンプルを保持し、音声では各 G.711 コードの下位ビットに回線ノイズや細かな成分が含まれ、どんなロスレス圧縮でも小さくできません。呼び出し音や無音は逆にほとんどゼロまで縮むため、多くの通話で平均すると g711xz は Opus に近く、MP3 よりかなり小さくなります。

### インストール

```bash
pip3 install g711xz
```

または GitHub から (Rust 拡張をビルドするため、Rust ツールチェーンと C コンパイラが必要です):

```bash
pip3 install git+https://github.com/wachawo/g711xz.git
```

### 使用方法

```bash
# ファイルのヘッダー、長さ、ビットレートを表示
g711xz info rec.g711.xz

# ロスレスのステレオ WAV にデコード (rec.wav に書き出し)
g711xz decode rec.g711.xz

# 指定したファイルにデコード
g711xz decode rec.g711.xz out.wav

# 2 チャンネル、16 ビット、8000 Hz の WAV をエンコード (rec.g711.xz に書き出し)
g711xz encode rec.wav

# もう一方の圧伸則に変換、ロスあり (u = mu-law、a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# ベータ: より小さい VOX ファイルを書き出し (完全な複製ではありません、rec.vox.g711.xz に書き出し)
g711xz encode rec.wav --vox

# VOX ファイルは他のファイルと同じように読めます。モードは info と decode の結果行に表示されます
g711xz decode rec.vox.g711.xz

# ヘルプを表示
g711xz --help
```

`g711xz info` の出力例:

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

### Python API

```python
import g711xz

# デコード: law は b"u" または b"a"、pcm は 8000 Hz のインターリーブされた s16le ステレオ
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# エンコード: .g711.xz ファイルのバイト列を返します
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# ベータの VOX ファイル: 書き出しは既定では無効で、読み込みは他のファイルと同じです
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# 元の録音そのものが必要ですか? モードを確認してください
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

PCM が純粋な G.711 でない場合、エンコードは `g711xz.RefusedError` を送出します。壊れたファイルを読み込むと `g711xz.FormatError` が送出されます。VOX ファイルはエラーではありません: `g711xz.read_mode` でロスレスのファイルと区別できます。

### 終了コード

| コード | 意味 |
|------|---------|
| 0    | 成功。 |
| 2    | 入力エラー: 壊れたファイルや別形式のファイル、形式の合わない WAV、存在しないファイル、誤った CLI 引数。 |
| 3    | エンコード拒否: PCM が純粋な G.711 ではないため、ロスレスのファイルを作成できません。 |

### コマンド

- `info FILE [FILE ...]` - ヘッダー、長さ、ビットレートを表示
- `decode FILE.g711.xz [OUT.wav]` - ロスレスのステレオ WAV にデコード
- `encode FILE.wav [OUT.g711.xz] [--vox]` - 2 チャンネル、16 ビット、8000 Hz の WAV をエンコード
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - もう一方の圧伸則に変換 (ロスあり)
- `--vox` - ベータ、`encode` のみ: VOX ファイルを書き出す。`info`、`decode`、`transcode` はどちらのモードも読み込み、モードを表示する
- `-h, --help` - ヘルプを表示

### 機能

- mu-law と A-law の録音を**ロスレスで往復変換**
- **厳格なエンコーダー**: 純粋な G.711 ではない音声は、ロスありで保存せずに拒否します
- **厳格なリーダー**: 壊れたファイル、途中で切れたファイル、大きすぎるファイルを拒否します
- **ストリーミングデコーダー**: PCM 全体をメモリ上に展開しません
- **圧伸則の相互変換** (mu-law と A-law)
- **オプションの高速化**: NumPy と Rust 拡張。なくてもピュア Python で動作します
- **クロスプラットフォーム** (Linux、macOS、Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - コマンド、Python API、検証ルール、エラーメッセージ、使用例の詳しいガイド。

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - `.g711.xz` の構造の仕様とテストベクター。独自のリーダーやライターを実装するのに十分な内容です。

### 開発ツール

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Rust 拡張をその場で再ビルド (Rust ツールチェーン、C コンパイラ、有効な virtualenv が必要)
maturin develop --release
```

### テスト

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# CI が coverage.xml を自動的に Codecov へアップロードします

# 標準ライブラリのみ
python3 -m unittest -v test_g711xz
```

### ライセンス

MIT License
