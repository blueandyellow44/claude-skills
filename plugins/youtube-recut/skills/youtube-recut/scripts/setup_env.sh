#!/usr/bin/env bash
# youtube-recut: one durable Python 3.11 env for every stage (ASR, denoise, zoom planning, cards).
# Idempotent: re-running only fills what is missing. Prints a one-line receipt per tool.
set -euo pipefail
ENV="${YR_ENV:-$HOME/.cache/youtube-recut/venv}"
command -v uv >/dev/null || { echo "uv not found: install with 'curl -LsSf https://astral.sh/uv/install.sh | sh'"; exit 1; }
[ -x "$ENV/bin/python" ] || uv venv --python 3.11 "$ENV"
# Pins that work together: DeepFilterNet 0.5.6 needs torch 2.5.x and numpy 1.x;
# OpenCV 5 dropped CascadeClassifier (face masking), so stay on 4.x.
uv pip install --python "$ENV/bin/python" \
  "numpy==1.26.4" "torch==2.5.1" "torchaudio==2.5.1" "deepfilternet==0.5.6" \
  "faster-whisper==1.2.1" "scipy>=1.11,<1.15" "soundfile>=0.12" "opencv-python-headless>=4.9,<4.11" "playwright>=1.45" "imageio-ffmpeg>=0.5" >/dev/null
"$ENV/bin/python" - <<'PY'
import numpy, scipy, torch, cv2, faster_whisper, df, imageio_ffmpeg, subprocess
ff = imageio_ffmpeg.get_ffmpeg_exe()
libass = 'subtitles' in subprocess.run([ff, '-hide_banner', '-filters'], capture_output=True, text=True).stdout
print(f"numpy {numpy.__version__} | torch {torch.__version__} | opencv {cv2.__version__} (CascadeClassifier {hasattr(cv2, 'CascadeClassifier')})")
print(f"faster-whisper {faster_whisper.__version__} | deepfilternet ok | ffmpeg {ff} (libass subtitles filter: {libass})")
PY
# Smoke-test the denoiser on a real file: torchaudio without a backend (no soundfile) killed a render
# 25 minutes in while "deepFilter exists" was true.
T=$(mktemp -d); "$ENV/bin/python" -c "import imageio_ffmpeg,subprocess;subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i','sine=f=440:d=1','-ar','48000','$T/t.wav'],check=True)"
"$ENV/bin/deepFilter" --atten-lim 12 -o "$T/o" "$T/t.wav" >/dev/null 2>&1 && ls "$T/o"/*.wav >/dev/null 2>&1 \
  && echo "deepFilter: processed a test file OK" || { echo "deepFilter FAILED on a test file"; exit 1; }
rm -rf "$T"
echo "ENV READY: $ENV"
