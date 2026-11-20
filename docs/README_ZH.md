## g711xz - G.711 通话录音的无损存储

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

以 PCMU 或 PCMA 穿过电话网络的每一通电话，本身就已经是压缩过的：每个 16 位采样最多只有 256 种取值。存成 WAV，每隔一个字节就是冗余的。存成 MP3 或 Opus，编解码器会悄悄改写音频，这些变化人耳几乎听不出来，语音识别却能察觉。

g711xz 原样保存通话。它把采样还原为 8 位 G.711 编码，用 xz 打包，并逐位还原出原始 PCM。振铃和静音几乎被压缩为零；对话占用的空间则比 Opus 大。它是一个命令行工具，也是一个纯 Python 库，支持 Linux、macOS 和 Windows。

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | **[中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md)** | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### 要求

- **Python 3.9 或更高版本**
- **Linux、macOS、Windows**：没有平台相关的要求
- **依赖**：无，仅需标准库
- **可选**：NumPy 或 Rust 扩展，存在时用作加速器

### 文件格式

一个文件对应一通录音：左声道是主叫方，右声道是被叫方。

- ✅ 无损：解码后逐位还原录音设备的 16 位 PCM
- ✅ mu-law (PCMU) 和 A-law (PCMA)
- ✅ 比对原始 PCM 直接用 xz 压缩小约四分之一
- ✅ 一个标准的 xz 流，仅用 `xz` 即可读取
- ❌ 非纯 G.711 的音频：直接拒绝，而不是取近似值
- ❌ 元数据：文件只包含音频，没有其他内容

### 对比

| | PCM | xz | g711xz | Opus 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|
| 能解码回原始音频 | 是 | 是 | 是 | 否 | 否 |
| 与原始转写稿相同的词, % | 100 | 100 | 100 | 94.9 | 94.4 |
| 转写稿逐词完全相同的通话, % | 100 | 100 | 100 | 71.9 | 65.7 |
| 平均体积, kbit/s | 256 | 28.6 | 21.8 | 20.8 | 32.4 |
| 5 分钟，MB | 9.60 | 1.07 | 0.82 | 0.78 | 1.22 |
| 编码 CPU，相对 Opus | 0 | 0.43 | 0.23 | 1 | 0.16 |

- **单独用 xz 也是无损的，只是更大。** 它压缩的是 16 位采样，而 g711xz 压缩的是生成这些采样的 8 位编码：xz 大约大 30%，CPU 消耗是两倍。
- **问题不在识别器。** 同一段音频转写两次，词的一致率为 100%，通话的一致率为 99.6%，所以 Opus 和 MP3 两列的差异来自编解码器。
- **为什么对话比 Opus 和 MP3 大。** 它们按目标码率编码，装不下的部分直接丢弃。g711xz 保留每一个采样，而在语音中，每个 G.711 编码的低位承载着线路噪声和细节，任何无损压缩都无法缩小。振铃和静音则相反：几乎被压缩为零，因此在大量通话中 g711xz 的体积接近 Opus，并明显小于 MP3。

### 安装

```bash
pip3 install g711xz
```

或从 GitHub 安装：

```bash
pip3 install git+https://github.com/wachawo/g711xz.git
```

### 使用方法

```bash
# 显示文件的头部、时长和码率
g711xz info rec.g711.xz

# 解码为无损立体声 WAV（写入 rec.wav）
g711xz decode rec.g711.xz

# 解码到指定文件
g711xz decode rec.g711.xz out.wav

# 编码 2 声道、16 位、8000 Hz 的 WAV（写入 rec.g711.xz）
g711xz encode rec.wav

# 转换为另一种压扩律，有损（u = mu-law，a = A-law）
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# 显示帮助
g711xz --help
```

`g711xz info` 的输出示例：

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

### Python API

```python
import g711xz

# 解码：law 为 b"u" 或 b"a"，pcm 为 8000 Hz 交错排列的 s16le 立体声
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# 编码：返回 .g711.xz 文件的字节内容
data = g711xz.encode(g711xz.read_wav("rec.wav"))
```

当 PCM 不是纯 G.711 时，编码会抛出 `g711xz.RefusedError`；读取损坏的文件时会抛出 `g711xz.FormatError`。

### 退出码

| 代码 | 含义 |
|------|---------|
| 0    | 成功。 |
| 2    | 输入有误：文件损坏或并非本格式、WAV 格式不符、文件不存在、命令行参数错误。 |
| 3    | 拒绝编码：PCM 不是纯 G.711，无法生成无损文件。 |

### 命令

- `info FILE [FILE ...]` - 显示头部、时长和码率
- `decode FILE.g711.xz [OUT.wav]` - 解码为无损立体声 WAV
- `encode FILE.wav [OUT.g711.xz]` - 编码 2 声道、16 位、8000 Hz 的 WAV
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - 转换为另一种压扩律（有损）
- `-h, --help` - 显示帮助

### 功能

- **无损往返**：支持 mu-law 和 A-law 录音
- **严格的编码器**：拒绝非纯 G.711 的音频，而不是有损保存
- **严格的读取器**：拒绝损坏、截断和超大的文件
- **流式解码器**：不会在内存中构建完整的 PCM
- **压扩律互转**（mu-law 与 A-law 互相转换）
- **可选加速器**：NumPy 和 Rust 扩展，并提供纯 Python 回退实现
- **跨平台**（Linux、macOS、Windows）

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - 关于命令、Python API、校验规则、错误信息和示例的完整指南。

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - `.g711.xz` 结构规范，附带测试向量，足以编写独立的读取器或写入器。

### 开发工具

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# 可选的 Rust 扩展（需要 Rust 工具链和已激活的 virtualenv）
maturin develop --release
```

### 测试

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# CI 会自动将 coverage.xml 上传到 Codecov

# 仅使用标准库
python3 -m unittest -v test_g711xz
```

### 许可证

MIT License
