from flask import Flask, request, jsonify
import cv2
import os
import uuid
import base64
import logging
import tempfile
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# Blur detection tuning
BLUR_THRESHOLD = 4.0      # frames below this are considered "blurry"
MAX_FRAMES = 15           # how many frames to extract
FRAME_MAX_WIDTH = 640     # resize output frames to this width
JPEG_QUALITY = 75         # 0-100, lower = smaller payload

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Extract clean, sharp key frames from any video. Blur-aware, fast, and built for automated pipelines.">
<title>VidLab — Key Frame Extraction</title>
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #f8fafc;
    --panel: #ffffff;
    --border: #e5e7eb;
    --border-strong: #d1d5db;
    --text: #0f172a;
    --text-muted: #64748b;
    --accent: #0f172a;
    --accent-hover: #1e293b;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
  }
  html, body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .panel { background: var(--panel); border: 1px solid var(--border); }
  .subtle-grid {
    background-image:
      linear-gradient(to right, rgba(15,23,42,0.04) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(15,23,42,0.04) 1px, transparent 1px);
    background-size: 32px 32px;
  }
  #drop { transition: border-color 0.15s ease, background-color 0.15s ease; }
  #drop.dragging { border-color: var(--accent); background: #f1f5f9; }
  .frame-card img { transition: transform 0.3s ease; }
  .frame-card:hover img { transform: scale(1.03); }
  details > summary { list-style: none; cursor: pointer; }
  details > summary::-webkit-details-marker { display: none; }
</style>
</head>
<body class="min-h-screen">

<!-- ─────────────── Nav ─────────────── -->
<header class="border-b border-gray-200 bg-white/80 backdrop-blur sticky top-0 z-20">
  <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
    <a href="/" class="flex items-center gap-2.5 group">
      <span class="inline-flex items-center justify-center w-8 h-8 rounded-md bg-slate-900 text-white">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="16" rx="2"/>
          <path d="M3 10h18M8 4v16M16 4v16"/>
        </svg>
      </span>
      <span class="font-bold tracking-tight text-slate-900 text-lg">Vid<span class="text-blue-600">Lab</span></span>
    </a>

    <nav class="flex items-center gap-1">
      <a href="https://github.com/NhlalwenhleShange/vidlab-app" target="_blank" rel="noopener"
         class="text-sm text-slate-600 hover:text-slate-900 px-3 py-2 rounded-md hover:bg-slate-100 transition-colors flex items-center gap-1.5">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
          <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.55v-2.14c-3.2.7-3.88-1.36-3.88-1.36-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.12 3.05.74.8 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.07.78 2.16v3.2c0 .3.21.66.79.55A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"/>
        </svg>
        Source
      </a>
    </nav>
  </div>
</header>

<!-- ─────────────── Main ─────────────── -->
<main class="max-w-6xl mx-auto px-6 py-12">

  <!-- Hero -->
  <section class="mb-10">
    <h1 class="text-3xl sm:text-4xl font-semibold tracking-tight text-slate-900 leading-tight">
      Extract clean, sharp key frames from any video
    </h1>
    <p class="mt-3 text-slate-600 max-w-2xl leading-relaxed">
      Upload a video and VidLab returns the crispest frames from across its duration.
      Blur detection filters out soft or motion-heavy shots, and a fallback ensures you
      always get results — even from compressed or low-light footage.
    </p>
  </section>

  <!-- Upload panel -->
  <section class="panel rounded-xl overflow-hidden">
    <div id="drop" class="subtle-grid relative px-6 sm:px-12 py-14 text-center border-b border-dashed border-gray-200 cursor-pointer">
      <div class="mx-auto w-14 h-14 rounded-full bg-slate-900 text-white flex items-center justify-center mb-5">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <h2 class="text-lg font-semibold text-slate-900">Upload a video</h2>
      <p class="text-sm text-slate-500 mt-1">
        Drag and drop your file here, or
        <span class="text-slate-900 font-medium underline underline-offset-2">browse</span>
      </p>
      <p class="text-xs text-slate-400 mt-3">MP4 · MOV · AVI · MKV · WebM &nbsp;·&nbsp; up to 200 MB</p>
      <input type="file" id="file" accept="video/*" class="hidden">
    </div>

    <!-- Status bar -->
    <div id="status" class="hidden px-6 py-4 border-b border-gray-200 bg-slate-50 text-sm text-slate-700 flex items-start gap-3">
      <span id="status-icon" class="flex-shrink-0 mt-0.5"></span>
      <span id="status-text" class="leading-relaxed"></span>
    </div>

    <!-- Results -->
    <div id="result-section" class="hidden p-6">
      <div class="flex items-baseline justify-between mb-4">
        <h3 class="text-sm font-semibold text-slate-900 uppercase tracking-wider">Extracted frames</h3>
        <span id="frame-count" class="text-xs text-slate-500"></span>
      </div>
      <div id="result" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"></div>

      <!-- Fallback notice -->
      <div id="fallback-notice" class="hidden mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 flex items-start gap-3">
        <svg class="flex-shrink-0 mt-0.5" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span>This video scored below the sharpness threshold for every sampled frame. The frames above are the sharpest available — they may look slightly soft.</span>
      </div>
    </div>
  </section>

  <!-- How it works -->
  <section class="mt-14 grid md:grid-cols-3 gap-6">
    <div>
      <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">01 — Sampling</div>
      <p class="text-sm text-slate-600 leading-relaxed">One frame per second is decoded across the full duration of the video, regardless of length or codec.</p>
    </div>
    <div>
      <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">02 — Scoring</div>
      <p class="text-sm text-slate-600 leading-relaxed">Each frame is scored by Laplacian variance — a measure of high-frequency edge energy — to estimate sharpness.</p>
    </div>
    <div>
      <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">03 — Selection</div>
      <p class="text-sm text-slate-600 leading-relaxed">Sharp frames are kept up to a limit of 15. If none pass, the highest-scoring frames are returned instead.</p>
    </div>
  </section>

</main>

<!-- ─────────────── Footer ─────────────── -->
<footer class="border-t border-gray-200 mt-16">
  <div class="max-w-6xl mx-auto px-6 py-8 text-xs text-slate-500">
    © 2026 VidLab · Built by Nhlalwenhle Shange
  </div>
</footer>

<script>
const drop          = document.getElementById('drop');
const fileInput     = document.getElementById('file');
const statusDiv     = document.getElementById('status');
const statusIcon    = document.getElementById('status-icon');
const statusText    = document.getElementById('status-text');
const resultSection = document.getElementById('result-section');
const resultGrid    = document.getElementById('result');
const frameCount    = document.getElementById('frame-count');
const fallbackNote  = document.getElementById('fallback-notice');

const ICON = {
  spinner: `<svg class="animate-spin" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9" stroke-opacity="0.2"/><path d="M21 12a9 9 0 0 0-9-9"/></svg>`,
  success: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
  error:   `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  info:    `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
};

function setStatus(kind, text) {
  statusDiv.classList.remove('hidden');
  statusIcon.innerHTML = ICON[kind] || ICON.info;
  statusText.innerHTML = text;
}

// Drag & drop
drop.addEventListener('click', () => fileInput.click());
['dragenter', 'dragover'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('dragging'); })
);
['dragleave', 'drop'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('dragging'); })
);
drop.addEventListener('drop', e => handle(e.dataTransfer.files[0]));
fileInput.addEventListener('change', () => handle(fileInput.files[0]));

async function handle(file) {
  if (!file) return;

  // Reset UI
  resultSection.classList.add('hidden');
  fallbackNote.classList.add('hidden');
  resultGrid.innerHTML = '';
  setStatus('spinner', `Uploading <span class="font-medium text-slate-900">${file.name}</span> — analyzing frames…`);

  const started = performance.now();
  const fd = new FormData();
  fd.append('video', file);

  try {
    const res = await fetch('/extract', { method: 'POST', body: fd });

    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
      const body = await res.text();
      console.error('Non-JSON response:', body);
      setStatus('error', 'Server returned an invalid response. Please try again.');
      return;
    }

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Processing failed.');

    const elapsed = ((performance.now() - started) / 1000).toFixed(1);

    if (!data.images || data.images.length === 0) {
      setStatus('info', 'No frames could be extracted. The video may be too short, corrupted, or in an unsupported codec.');
      return;
    }

    // Render
    frameCount.textContent = `${data.frames} frame${data.frames === 1 ? '' : 's'} · ${elapsed}s`;
    resultSection.classList.remove('hidden');

    data.images.forEach((src, i) => {
      const card = document.createElement('a');
      card.href = src;
      card.target = '_blank';
      card.rel = 'noopener';
      card.download = `frame-${String(i + 1).padStart(2, '0')}.jpg`;
      card.className = 'frame-card group relative block aspect-video rounded-lg overflow-hidden border border-gray-200 bg-slate-100';
      card.innerHTML = `
        <img src="${src}" alt="Frame ${i + 1}" loading="lazy" class="w-full h-full object-cover">
        <span class="absolute top-1.5 left-1.5 text-[10px] font-medium text-white bg-black/55 backdrop-blur px-1.5 py-0.5 rounded">
          ${String(i + 1).padStart(2, '0')}
        </span>
        <span class="absolute inset-x-0 bottom-0 p-1.5 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
          <span class="text-[10px] text-white/90">Open full size</span>
        </span>
      `;
      resultGrid.appendChild(card);
    });

    if (data.fallback_used) {
      fallbackNote.classList.remove('hidden');
      setStatus('info', `Extracted <span class="font-medium text-slate-900">${data.frames}</span> frames using the sharpest-frame fallback.`);
    } else {
      setStatus('success', `Extracted <span class="font-medium text-slate-900">${data.frames}</span> sharp frames from <span class="font-medium text-slate-900">${file.name}</span>.`);
    }

  } catch (err) {
    console.error(err);
    setStatus('error', err.message || 'Something went wrong during processing.');
  }
}
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return HTML_PAGE


@app.route("/health")
def health():
    return {"status": "healthy", "service": "vidlab-app"}


@app.route("/diag")
def diag():
    """Diagnostic endpoint — confirms OpenCV, numpy, and ffmpeg are all available."""
    import numpy
    info = cv2.getBuildInformation()
    ffmpeg_line = next((l.strip() for l in info.splitlines() if "FFMPEG" in l), "not found")
    return {
        "opencv": cv2.__version__,
        "numpy": numpy.__version__,
        "ffmpeg_binary": os.popen("which ffmpeg").read().strip() or "NOT FOUND",
        "ffmpeg_build": ffmpeg_line,
        "blur_threshold": BLUR_THRESHOLD,
        "max_frames": MAX_FRAMES,
    }


def compute_variance(image):
    """Return the Laplacian variance (sharpness score) of a frame."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def resize_frame(frame, max_width=FRAME_MAX_WIDTH):
    """Resize frame to reduce base64 payload size significantly."""
    h, w = frame.shape[:2]
    if w > max_width:
        scale = max_width / w
        new_h = int(h * scale)
        frame = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)
    return frame


def encode_frame(frame):
    """Encode a BGR frame as a data-URI JPEG string. Returns None on failure."""
    small = resize_frame(frame, max_width=FRAME_MAX_WIDTH)
    success, buffer = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not success:
        return None
    encoded = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


@app.route("/extract", methods=["POST"])
def extract_frames():
    logger.info(f"Incoming files: {list(request.files.keys())}")
    file = request.files.get("video")
    if not file or file.filename == "":
        return jsonify({"error": "No valid video file uploaded."}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Invalid file format '{ext}'."}), 400

    # Use tempfile for Azure compatibility
    tmp_dir = tempfile.mkdtemp()
    tmp_id = str(uuid.uuid4())
    tmp_path = os.path.join(tmp_dir, f"{tmp_id}{ext}")

    try:
        file.save(tmp_path)
        logger.info(f"Saved video to {tmp_path}, size: {os.path.getsize(tmp_path)} bytes")

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return jsonify({"error": "Could not open video file. Codec may not be supported."}), 400

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 30.0
        frame_interval = max(1, int(fps))

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        logger.info(
            f"Video: {width}x{height}, FPS={fps:.2f}, "
            f"frames={frame_count}, duration={duration:.1f}s, "
            f"sampling every {frame_interval} frames"
        )

        # Collect every sampled frame with its variance
        all_frames = []  # list of (variance, data_uri)
        count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if count % frame_interval == 0:
                variance = compute_variance(frame)
                logger.info(f"Frame {count}: variance={variance:.2f}")

                encoded = encode_frame(frame)
                if encoded:
                    all_frames.append((variance, encoded))

            count += 1

        cap.release()

        # Pass 1: keep frames that clear the blur threshold, up to MAX_FRAMES
        thumbnails = []
        saved = 0
        for variance, encoded in all_frames:
            if variance >= BLUR_THRESHOLD:
                thumbnails.append(encoded)
                saved += 1
                if saved >= MAX_FRAMES:
                    break

        fallback_used = False

        # Pass 2: if nothing passed, fall back to the sharpest available frames
        if saved == 0 and all_frames:
            logger.info("No frames passed blur filter — using sharpest available.")
            all_frames.sort(key=lambda x: x[0], reverse=True)
            for _, encoded in all_frames[:MAX_FRAMES]:
                thumbnails.append(encoded)
                saved += 1
            fallback_used = True

        total_kb = sum(len(t) for t in thumbnails) // 1024
        logger.info(
            f"Extracted {saved} frames total. "
            f"Response size approx: {total_kb} KB. "
            f"Fallback used: {fallback_used}"
        )

        return jsonify({
            "frames": saved,
            "images": thumbnails,
            "fallback_used": fallback_used,
        })

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)