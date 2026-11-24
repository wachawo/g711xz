## g711xz - хранение записей звонков G.711 без потерь

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Любой звонок, который проходит через телефонную сеть как PCMU или PCMA, уже сжат: каждый 16-битный отсчёт принимает одно из не более чем 256 значений. Сохраните его в WAV, и каждый второй байт окажется лишним. Сохраните в MP3 или Opus, и кодек незаметно перепишет звук: человек этих изменений почти не слышит, а распознаватель речи слышит.

g711xz хранит звонок ровно таким, каким он пришёл. Он возвращает отсчёты в их 8-битные коды G.711, сжимает их xz и отдаёт исходный PCM бит в бит. Гудки и тишина сжимаются почти в ноль, а разговор занимает больше места, чем Opus. Это утилита командной строки и библиотека Python для Linux, macOS и Windows, а в опубликованных колёсах есть расширение на Rust.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | **[Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md)** | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Требования

- **Python 3.9 или выше**
- **Linux, macOS, Windows**: требований, зависящих от платформы, нет
- **Зависимости**: нет, достаточно стандартной библиотеки
- **Опционально**: NumPy или расширение на Rust, которые используются как ускорители, если установлены

### Формат файла

Один файл - это одна запись звонка: левый канал - звонящий, правый канал - вызываемый абонент.

- ✅ Без потерь: декодирование возвращает 16-битный PCM рекордера бит в бит
- ✅ mu-law (PCMU) и A-law (PCMA)
- ✅ Примерно на четверть меньше, чем xz по сырому PCM
- ✅ Один стандартный поток xz, читается одной утилитой `xz`
- ❌ Звук, который не является чистым G.711: отклоняется, а не округляется
- ❌ Метаданные: в файле только звук и больше ничего

### Сравнение

| | ULAW | XZ | G711XZ | G711XZ VOX | OPUS 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|---|
| Декодируется обратно в оригинал | да | да | да | только речь | нет | нет |
| Слов как в расшифровке оригинала, % | 100 | 100 | 100 | 99.96 | 94.6 | 95.0 |
| Звонков с расшифровкой слово в слово, % | 100 | 100 | 100 | 99.87 | 71.7 | 71.4 |
| Средний размер, kbit/s | 128 | 23.7 | 20.8 | 18.4 | 20.6 | 32.4 |
| 5 минут, MB | 4.80 | 0.89 | 0.78 | 0.69 | 0.77 | 1.22 |
| CPU на кодирование, % от Opus | 0 | 24 | 13 | 12 | 100 | 16 |

ULAW - исходный поток mu-law, стерео 8 kHz. XZ - это `xz -6` поверх этих байтов, OPUS - `opusenc --bitrate 32 --speech`, MP3 - `lame -b 32`. Строки про расшифровку сравнивают расшифровку Whisper для каждого формата с расшифровкой исходного звука.

- **xz сам по себе тоже без потерь, просто больше.** Он берёт байты как есть, а g711xz сначала раскладывает каждую сторону звонка отдельно: xz выходит примерно на 14% больше и тратит вдвое больше CPU.
- **G711XZ VOX - это бета-режим VOX** (`g711xz encode in.wav --vox`), по умолчанию выключен. Речь сохраняется бит в бит, а длинные участки ровного шума линии заменяются, поэтому файл меньше, но это уже не точная копия. Любой читатель версии 0.0.3 открывает его как файл без потерь, а `g711xz info` показывает режим. См. [VOX Mode (Beta)](FEATURES.md#vox-mode-beta).
- **Распознаватель не виноват.** Один и тот же звук, распознанный дважды, совпадает в 99,98% слов и в 99,8% звонков, так что расхождения в столбцах Opus и MP3 дают кодеки.
- **Почему разговор больше, чем Opus и MP3.** Они работают под заданный битрейт и выбрасывают всё, что не влезло. g711xz хранит каждый отсчёт, а в речи младшие биты каждого кода G.711 несут шум линии и мелкие детали, которые не сожмёт ни один компрессор без потерь. Гудки и тишина работают наоборот: сжимаются почти в ноль, поэтому на множестве звонков g711xz выходит близко к Opus и заметно меньше MP3.

### Установка

```bash
pip3 install g711xz
```

Или из GitHub (при этом собирается расширение на Rust, нужны тулчейн Rust и компилятор C):

```bash
sudo apt install git curl build-essential python3-pip
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Использование

```bash
# Показать заголовок, длительность и битрейт файла
g711xz info rec.g711.xz

# Декодировать в стерео WAV без потерь (запишет rec.wav)
g711xz decode rec.g711.xz

# Декодировать в указанный файл
g711xz decode rec.g711.xz out.wav

# Закодировать WAV: 2 канала, 16 бит, 8000 Гц (запишет rec.g711.xz)
g711xz encode rec.wav

# Перекодировать в другой закон, с потерями (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Бета: записать файл VOX поменьше, не точную копию (запишет rec.vox.g711.xz)
g711xz encode rec.wav --vox

# Файл VOX читается как любой другой; режим показывают info и строка результата decode
g711xz decode rec.vox.g711.xz

# Показать справку
g711xz --help
```

Пример вывода `g711xz info`:

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

# Декодирование: law равен b"u" или b"a", pcm - чередующийся стерео s16le, 8000 Гц
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Кодирование: возвращает байты файла .g711.xz
data = g711xz.encode(g711xz.read_wav("rec.wav"))

# Бета-файл VOX: при записи по умолчанию выключен, читается как любой другой файл
data = g711xz.encode(g711xz.read_wav("rec.wav"), vox=True)
law, frames, pcm = g711xz.decode(data)

# Нужна точная запись? Проверьте режим
exact = g711xz.read_mode(data) != g711xz.MODE_VOX
```

Кодирование вызывает `g711xz.RefusedError`, если PCM не является чистым G.711, а чтение вызывает `g711xz.FormatError` для повреждённого файла. Файл VOX - не ошибка: `g711xz.read_mode` отличает его от файла без потерь.

### Коды возврата

| Код | Значение |
|------|---------|
| 0    | Успех. |
| 2    | Некорректный ввод: повреждённый или чужой файл, WAV не того формата, отсутствующий файл, неверные аргументы CLI. |
| 3    | Отказ в кодировании: PCM не является чистым G.711, поэтому файл без потерь создать нельзя. |

### Команды

- `info FILE [FILE ...]` - Показать заголовок, длительность и битрейт
- `decode FILE.g711.xz [OUT.wav]` - Декодировать в стерео WAV без потерь
- `encode FILE.wav [OUT.g711.xz] [--vox]` - Закодировать WAV: 2 канала, 16 бит, 8000 Гц
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - Перекодировать в другой закон (с потерями)
- `--vox` - Бета, только для `encode`: записать файл VOX. `info`, `decode` и `transcode` читают оба режима и называют режим
- `-h, --help` - Показать справку

### Возможности

- **Кодирование и декодирование без потерь** для записей mu-law и A-law
- **Строгий кодировщик**: отклоняет звук, который не является чистым G.711, вместо сохранения с потерями
- **Строгое чтение**: отклоняет повреждённые, обрезанные и слишком большие файлы
- **Потоковый декодер**, который не собирает весь PCM в памяти
- **Перекодирование между законами** (mu-law в A-law и обратно)
- **Опциональные ускорители**: NumPy и расширение на Rust, с запасным вариантом на чистом Python
- **Кроссплатформенность** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Подробное руководство по командам, Python API, правилам проверки, сообщениям об ошибках и примерам.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Спецификация устройства `.g711.xz` с тестовым вектором, достаточная для написания независимого читателя или кодировщика.

### Инструменты разработки

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Пересобрать расширение на Rust на месте (нужны тулчейн Rust, компилятор C и активный virtualenv)
maturin develop --release
```

### Тестирование

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# CI автоматически загружает coverage.xml в Codecov

# Только стандартная библиотека
python3 -m unittest -v test_g711xz
```

### Лицензия

MIT License
