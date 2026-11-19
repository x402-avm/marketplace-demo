# Third-Party Software Notices and Licences

This project integrates or references open-source third-party libraries, models, and runtimes across the service fleet. This document provides notice of all included, wrapped, or vendored third-party components and their respective licences.

---

## Confirmed Open Source Licences

### 1. Model Weights & Voice Libraries
- **Kokoro-82M TTS Model (`kokoro-v1.0.onnx`, `voices-v1.0.bin`)**
  - **Licence**: Apache-2.0
  - **Source / URL**: https://huggingface.co/hexgrad/Kokoro-82M and https://github.com/thewh1teagle/kokoro-onnx
  - **Copyright**: Copyright (c) 2025 hexgrad, @thewh1teagle

### 2. Python Libraries & MCP Components
- **kokoro-onnx** (`servers/tts`)
  - **Licence**: MIT
  - **URL**: https://github.com/thewh1teagle/kokoro-onnx
  - **Copyright**: Copyright (c) 2024-2025 @thewh1teagle

- **RapidOCR (`rapidocr-onnxruntime`)** (`servers/ocr_mcp`)
  - **Licence**: Apache-2.0
  - **URL**: https://github.com/RapidAI/RapidOCR
  - **Copyright**: Copyright (c) 2021-2025 RapidAI

- **LaTeX-OCR (`pix2tex`)** (`servers/ocr_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/lukas-blecher/LaTeX-OCR
  - **Copyright**: Copyright (c) 2021 Lukas Blecher

- **ZXing-C++ (`zxing-cpp`)** (`servers/ocr_mcp`)
  - **Licence**: Apache-2.0
  - **URL**: https://github.com/zxing-cpp/zxing-cpp
  - **Copyright**: Copyright (c) 2020 ZXing-C++ Authors

- **pdf-mcp** (`servers/pdf_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/kevinsjtan/pdf-mcp
  - **Copyright**: Copyright (c) 2025 Kevin Tan

- **pdf-reader-mcp** (`servers/pdf_reader_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/SylphxAI/pdf-reader-mcp
  - **Copyright**: Copyright (c) 2024-2026 SylphxAI

- **FastMCP & FastMCP-slim** (`servers/*`)
  - **Licence**: MIT / Apache-2.0
  - **URL**: https://github.com/jlowin/fastmcp
  - **Copyright**: Copyright (c) 2024 Jeremiah Lowin

- **MoviePy (`moviepy`)** (`servers/video_edit_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/Zulko/moviepy
  - **Copyright**: Copyright (c) 2015 Zulko

- **Pillow** (`servers/conversion_mcp`, `servers/image_edit_mcp`, `servers/ocr_mcp`)
  - **Licence**: HPND / Historical Permission Notice and Disclaimer (MIT-equivalent)
  - **URL**: https://github.com/python-pillow/Pillow
  - **Copyright**: Copyright (c) 2010-2025 Jeffrey A. Clark (Alex) and contributors

- **ReportLab** (`servers/invoice_mcp`, `servers/resume_mcp`)
  - **Licence**: BSD-3-Clause
  - **URL**: https://www.reportlab.com/
  - **Copyright**: Copyright (c) 2000-2025 ReportLab Inc.

- **Playwright (`playwright`)** (`servers/web_mcp`)
  - **Licence**: Apache-2.0
  - **URL**: https://github.com/microsoft/playwright-python
  - **Copyright**: Copyright (c) Microsoft Corporation

- **playwright-stealth** (`servers/web_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/AtuboDad/playwright_stealth
  - **Copyright**: Copyright (c) 2021 AtuboDad

- **yt-dlp** (`servers/yt_mcp`)
  - **Licence**: The Unlicense (Public Domain dedication)
  - **URL**: https://github.com/yt-dlp/yt-dlp
  - **Copyright**: Public Domain

- **youtube-transcript-api** (`servers/yt_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/jdepoix/youtube-transcript-api
  - **Copyright**: Copyright (c) 2019 Jonas Depoix

- **python-whois** (`servers/domain_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/richardpenman/whois
  - **Copyright**: Copyright (c) 2014-2025 Richard Penman

- **dnspython** (`servers/domain_mcp`)
  - **Licence**: ISC Licence
  - **URL**: https://github.com/rthalley/dnspython
  - **Copyright**: Copyright (c) 2001-2025 Nominum, Inc.

- **duckduckgo-search** (`servers/web_mcp`)
  - **Licence**: MIT
  - **URL**: https://github.com/deedy5/duckduckgo_search
  - **Copyright**: Copyright (c) 2021-2025 deedy5

- **OpenPyXL** (`servers/conversion_mcp`)
  - **Licence**: MIT
  - **URL**: https://foss.heptapod.net/openpyxl/openpyxl
  - **Copyright**: Copyright (c) 2010-2025 Eric Gazoni, Charlie Clark

---

## Needs Review

The following components are utilized as system utilities or transitive dependencies with copyleft or dual-licensing terms that warrant verification before commercial redistribution:

1. **PyMuPDF (`fitz`)** (`servers/ocr_mcp`, `servers/pdf_mcp` dependency)
   - **Licence**: GNU AGPL v3.0 / Commercial
   - **URL**: https://github.com/pymupdf/PyMuPDF
   - **Notes**: PyMuPDF is released under AGPL v3.0. Distribution of binaries or software incorporating PyMuPDF requires compliance with AGPL copyleft requirements or obtaining a commercial license from Artifex Software.

2. **TeX Live / pdfLaTeX** (`servers/latex_mcp`)
   - **Licence**: GPL v2.0+ / LPPL (LaTeX Project Public License)
   - **URL**: https://www.tug.org/texlive/
   - **Notes**: `latex_mcp` invokes the host system `pdflatex` CLI as an external subprocess; not compiled or statically linked.

3. **FFmpeg / imageio-ffmpeg** (`servers/video_edit_mcp`)
   - **Licence**: GNU LGPL v2.1+ / GPL v2.0+ (depending on build flags and enabled codecs)
   - **URL**: https://ffmpeg.org / https://github.com/imageio/imageio-ffmpeg
   - **Notes**: `imageio-ffmpeg` downloads or wraps an external FFmpeg binary. Exact licensing depends on compilation options (e.g., `--enable-gpl` or `--enable-nonfree`).
