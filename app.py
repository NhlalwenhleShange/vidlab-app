from flask import Flask, request, jsonify
import cv2
import os
import uuid
import base64
import logging
from pathlib import Path

# Configure professional logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Allowed video extensions
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
<title>VidLab - AI Video Frame Extractor</title>
</head>
<body class="bg-gray-50 min-h-screen text-gray-800">
<div class="max-w-4xl mx-auto p-6">
  <header class="flex justify-between items-center mb-8">
    <div>
      <h1 class="text-2xl font-bold">Vid<span class="text-blue-600">Lab</span></h1>
      <p class="text-xs text-gray-500">Cloud-Native Video Processing Pipeline</p>
    </div>
    <span class="text-xs bg-green-100 text-green-700 font-medium px-3 py-1 rounded-full flex items-center gap-1">
      <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> Live in Azure
    </span>
  </header>

  <main class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
    <h2 class="text-xl font-semibold mb-1">Upload your video</h2>
    <p class="text-gray-500 text-sm mb-6">Extracts up to 15 key frames • AI blur detection • Cloud-ready</p>

    <div id="drop" class="border-2 border-dashed border-gray-200 rounded-xl p-10 text-center hover:border-blue-500 transition-colors cursor-pointer bg-gray-50/50">
      <div class="text-5xl mb-3">🎬</div>
      <p class="font-medium text-gray-700">Drag & drop your video here, or <span class="text-blue-600 underline">browse</span></p>
      <p class="text-xs text-gray-400 mt-1">MP4, MOV, AVI up to 200MB</p>
      <input type="file" id="file" accept="video/*" class="hidden">
    </div>

    <div id="status" class="hidden mt-6 p-4 bg-blue-50 border border-blue-100 rounded-xl text-sm text-blue-800 font-medium"></div>
    
    <!-- Gallery Preview Grid -->
    <div id="result-section" class="hidden mt-8">
      <h3 class="font-semibold text-gray-700 mb-3">Extracted Frames Preview</h3>
      <div id="result" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3"></div>
    </div>
  </main>

  <footer class="mt-8 grid grid-cols-3 gap-4 text-center text-xs">
    <div class="bg-white p-4 rounded-xl border border-gray-100 shadow-sm"><div class="font-bold text-gray-800 text-sm">OpenCV</div><div class="text-gray-400 mt-0.5">Frame Engine</div></div>
    <div class="bg-white p-4 rounded-xl border border-gray-100 shadow-sm"><div class="font-bold text-gray-800 text-sm">Azure Blob</div><div class="text-gray-400 mt-0.5">Cloud Storage</div></div>
    <div class="bg-white p-4 rounded-xl border border-gray-100 shadow-sm"><div class="font-bold text-gray-800 text-sm">Container Apps</div><div class="text-gray-400 mt-0.5">Serverless Host</div></div>
  </footer>
</div>

<script>
const drop = document.getElementById('drop');
const fileInput = document.getElementById('file');
const statusDiv = document.getElementById('status');
const resultSection = document.getElementById('result-section');
const resultGrid = document.getElementById('result');

drop.onclick = () => fileInput.click();
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('border-blue-500', 'bg-blue-50/2id'); };
drop.ondragleave = () => drop.classList.remove('border-blue-500', 'bg-blue-50/20');
drop.ondrop = (e) => { e.preventDefault(); handle(e.dataTransfer.files[0]); };
fileInput.onchange = () => handle(fileInput.files[0]);

async function handle(file){
  if(!file) return;
  
  statusDiv.classList.remove('hidden');
  resultSection.classList.add('hidden');
  resultGrid.innerHTML = '';
  statusDiv.innerHTML = `⏳ Uploading "${file.name}" and extracting clear frames...`;

  const fd = new FormData(); 
  fd.append('video', file);

  try {
    const res = await fetch('/extract', {method:'POST', body: fd});
    const data = await res.json();

    if(!res.ok){
      throw new Error(data.error || 'Processing failed');
    }

    statusDiv.innerHTML = `✅ Success! Extracted ${data.frames} clear, non-blurry frames.`;
    
    if(data.images && data.images.length > 0) {
      resultSection.classList.remove('hidden');
      data.images.forEach((imgSrc, idx) => {
        const card = document.createElement('div');
        card.className = "relative group overflow-hidden rounded-lg border border-gray-200 bg-gray-100 aspect-video flex items-center justify-center";
        card.innerHTML = `<img src="${imgSrc}" class="object-cover w-full h-full hover:scale-105 transition-transform duration-300" alt="Frame ${idx + 1}">
                          <span class="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded">#${idx + 1}</span>`;
        resultGrid.appendChild(card);
      });
    }
  } catch (err) {
    statusDiv.innerHTML = `❌ Error: ${err.message}`;
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

def is_blurry(image, threshold=40.0):
    """Calculates variance of Laplacian to determine blurriness."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    logger.info(f"Frame Laplacian variance score: {variance}")
    return variance < threshold

@app.route("/extract", methods=["POST"])
def extract_frames():
    file = request.files.get("video")
    if not file or file.filename == "":
        return jsonify({"error": "No valid video file uploaded."}), 400

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Invalid file format '{ext}'. Allowed formats: MP4, MOV, AVI, MKV."}), 400

    tmp_id = str(uuid.uuid4())
    tmp_path = f"/tmp/{tmp_id}{ext}"
    output_dir = f"/tmp/frames_{tmp_id}"
    Path(output_dir).mkdir(exist_ok=True)

    try:
        file.save(tmp_path)
        logger.info(f"Saved incoming video to {tmp_path}")

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return jsonify({"error": "Could not open video file."}), 400

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        count, saved = 0, 0
        thumbnails = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Extract roughly 1 frame per second
            if count % int(fps) == 0:
                if not is_blurry(frame):
                    frame_path = f"{output_dir}/frame_{saved}.jpg"
                    cv2.imwrite(frame_path, frame)

                    # Encode thumbnail for instant browser preview
                    with open(frame_path, "rb") as img_file:
                        encoded = base64.b64encode(img_file.read()).decode("utf-8")
                        thumbnails.append(f"data:image/jpeg;base64,{encoded}")

                    saved += 1

            count += 1
            if saved >= 15:
                break

        cap.release()
        logger.info(f"Successfully extracted {saved} clear frames.")

        return jsonify({"frames": saved, "images": thumbnails})

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        return jsonify({"error": "An internal error occurred during video processing."}), 500

    finally:
        # Cleanup temporary video file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)