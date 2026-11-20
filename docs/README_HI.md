## g711xz - G.711 कॉल रिकॉर्डिंग का लॉसलेस भंडारण

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

PCMU या PCMA के रूप में फ़ोन नेटवर्क से गुज़रने वाली हर कॉल पहले से ही संपीड़ित होती है: हर 16-बिट सैंपल के अधिकतम 256 मान ही हो सकते हैं। इसे WAV में सहेजें तो हर दूसरा बाइट बेकार है। इसे MP3 या Opus में सहेजें तो कोडेक चुपचाप ऑडियो को बदल देता है, ऐसे बदलाव जिन्हें इंसान मुश्किल से सुनता है पर स्पीच रिकग्नाइज़र पकड़ लेता है।

g711xz कॉल को ठीक वैसा ही रखता है जैसी वह आई थी। यह सैंपल को वापस उनके 8-बिट G.711 कोड में बदलता है, उन्हें xz से पैक करता है और मूल PCM को बिट-दर-बिट लौटाता है। रिंगिंग और सन्नाटा लगभग शून्य तक सिकुड़ जाते हैं; बातचीत Opus से ज़्यादा जगह लेती है। यह Linux, macOS और Windows के लिए एक कमांड लाइन टूल और शुद्ध Python लाइब्रेरी है।

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Español](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | **[हिन्दी](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)**

### आवश्यकताएं

- **Python 3.9 या उससे ऊपर**
- **Linux, macOS, Windows**: प्लेटफ़ॉर्म-विशिष्ट कोई आवश्यकता नहीं
- **निर्भरताएं**: कोई नहीं, मानक लाइब्रेरी पर्याप्त है
- **वैकल्पिक**: NumPy या Rust एक्सटेंशन, जो मौजूद होने पर गति बढ़ाने के लिए उपयोग होते हैं

### फ़ाइल प्रारूप

एक फ़ाइल एक रिकॉर्ड की गई कॉल है: बायां चैनल कॉल करने वाला है, दायां चैनल कॉल पाने वाला है।

- ✅ लॉसलेस: डिकोडिंग रिकॉर्डर का 16-बिट PCM बिट-दर-बिट लौटाती है
- ✅ mu-law (PCMU) और A-law (PCMA)
- ✅ कच्चे PCM पर xz से लगभग एक चौथाई छोटा
- ✅ एक मानक xz स्ट्रीम, जिसे केवल `xz` से पढ़ा जा सकता है
- ❌ जो ऑडियो शुद्ध G.711 नहीं है: उसे राउंड करने के बजाय अस्वीकार किया जाता है
- ❌ मेटाडेटा: फ़ाइल में केवल ऑडियो होता है, और कुछ नहीं

### तुलना

| | PCM | xz | g711xz | Opus 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|
| वापस मूल में डिकोड होता है | हाँ | हाँ | हाँ | नहीं | नहीं |
| मूल ट्रांसक्रिप्ट से मेल खाते शब्द, % | 100 | 100 | 100 | 94.9 | 94.4 |
| शब्दशः समान ट्रांसक्रिप्ट वाली कॉल, % | 100 | 100 | 100 | 71.9 | 65.7 |
| औसत आकार, kbit/s | 256 | 28.6 | 21.8 | 20.8 | 32.4 |
| 5 मिनट, MB | 9.60 | 1.07 | 0.82 | 0.78 | 1.22 |
| एनकोड करने में CPU, Opus की तुलना में | 0 | 0.43 | 0.23 | 1 | 0.16 |

- **अकेला xz भी लॉसलेस है, बस बड़ा।** यह 16-बिट सैंपल को संपीड़ित करता है, जबकि g711xz उन 8-बिट कोड को जिनसे वे बने थे: xz लगभग 30% बड़ा निकलता है और दोगुना CPU लेता है।
- **रिकग्नाइज़र दोषी नहीं है।** एक ही ऑडियो को दो बार ट्रांसक्राइब करने पर 100% शब्द और 99.6% कॉल मेल खाती हैं, इसलिए Opus और MP3 कॉलम का अंतर कोडेक से आता है।
- **बातचीत Opus और MP3 से बड़ी क्यों होती है।** ये एक तय बिटरेट पर काम करते हैं और जो नहीं समाता उसे फेंक देते हैं। g711xz हर सैंपल रखता है, और बोली में हर G.711 कोड के निचले बिट लाइन का शोर और बारीक विवरण लिए होते हैं, जिन्हें कोई लॉसलेस कंप्रेसर छोटा नहीं कर सकता। रिंगिंग और सन्नाटा उल्टा काम करते हैं: वे लगभग शून्य तक सिकुड़ जाते हैं, इसलिए बहुत सी कॉल पर g711xz, Opus के करीब और MP3 से काफ़ी छोटा रहता है।

### स्थापना

```bash
pip3 install g711xz
```

या GitHub से:

```bash
pip3 install git+https://github.com/wachawo/g711xz.git
```

### उपयोग

```bash
# फ़ाइल का हेडर, अवधि और बिटरेट दिखाएं
g711xz info rec.g711.xz

# लॉसलेस स्टीरियो WAV में डिकोड करें (rec.wav लिखता है)
g711xz decode rec.g711.xz

# चुनी हुई फ़ाइल में डिकोड करें
g711xz decode rec.g711.xz out.wav

# 2-चैनल, 16-बिट, 8000 Hz WAV को एनकोड करें (rec.g711.xz लिखता है)
g711xz encode rec.wav

# दूसरे लॉ में बदलें, हानि के साथ (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# सहायता दिखाएं
g711xz --help
```

`g711xz info` के आउटपुट का उदाहरण:

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

# डिकोड: law b"u" या b"a" होता है, pcm 8000 Hz पर इंटरलीव्ड s16le स्टीरियो है
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# एनकोड: .g711.xz फ़ाइल के बाइट लौटाता है
data = g711xz.encode(g711xz.read_wav("rec.wav"))
```

जब PCM शुद्ध G.711 नहीं होता तो एनकोडिंग `g711xz.RefusedError` देती है, और क्षतिग्रस्त फ़ाइल पढ़ने पर `g711xz.FormatError` मिलता है।

### एग्ज़िट कोड

| कोड | अर्थ |
|------|---------|
| 0    | सफलता। |
| 2    | गलत इनपुट: क्षतिग्रस्त या किसी और प्रारूप की फ़ाइल, गलत प्रारूप वाला WAV, अनुपस्थित फ़ाइल, गलत CLI आर्ग्युमेंट। |
| 3    | एनकोड अस्वीकृत: PCM शुद्ध G.711 नहीं है, इसलिए लॉसलेस फ़ाइल नहीं बनाई जा सकती। |

### कमांड

- `info FILE [FILE ...]` - हेडर, अवधि और बिटरेट दिखाएं
- `decode FILE.g711.xz [OUT.wav]` - लॉसलेस स्टीरियो WAV में डिकोड करें
- `encode FILE.wav [OUT.g711.xz]` - 2-चैनल, 16-बिट, 8000 Hz WAV को एनकोड करें
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - दूसरे लॉ में बदलें (हानि के साथ)
- `-h, --help` - सहायता दिखाएं

### सुविधाएं

- mu-law और A-law रिकॉर्डिंग के लिए **लॉसलेस राउंड ट्रिप**
- **सख्त एनकोडर**: जो ऑडियो शुद्ध G.711 नहीं है उसे हानि के साथ सहेजने के बजाय अस्वीकार करता है
- **सख्त रीडर**: क्षतिग्रस्त, अधूरी और बहुत बड़ी फ़ाइलों को अस्वीकार करता है
- **स्ट्रीमिंग डिकोडर** जो पूरा PCM कभी मेमोरी में नहीं बनाता
- **लॉ के बीच रूपांतरण** (mu-law से A-law और वापस)
- **वैकल्पिक एक्सेलरेटर**: NumPy और Rust एक्सटेंशन, साथ में शुद्ध Python फ़ॉलबैक
- **क्रॉस-प्लेटफ़ॉर्म** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - कमांड, Python API, सत्यापन नियमों, त्रुटि संदेशों और उदाहरणों की विस्तृत मार्गदर्शिका।

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - `.g711.xz` की संरचना का विनिर्देश, एक टेस्ट वेक्टर के साथ, जो स्वतंत्र रीडर या राइटर लिखने के लिए पर्याप्त है।

### विकास उपकरण

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# वैकल्पिक Rust एक्सटेंशन (Rust टूलचेन और सक्रिय virtualenv आवश्यक)
maturin develop --release
```

### परीक्षण

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# CI अपने आप coverage.xml को Codecov पर अपलोड करता है

# केवल मानक लाइब्रेरी से
python3 -m unittest -v test_g711xz
```

### लाइसेंस

MIT License
