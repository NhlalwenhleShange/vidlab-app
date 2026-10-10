from flask import Flask, request, jsonify
import cv2, os, uuid
from pathlib import Path

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
<title>FrameExtract - Video to Images</title>
</head>
<body class="bg-gray-50 min-h-screen">
<div class="max-w-4xl mx-auto p-6">
  <div class="flex justify-between items-center mb-8">
    <h1 class="text-2xl font-bold">Frame<span class="text-blue-600">Extract</span></h1>
    <span class="text-sm bg-green-100 text-green-700 px-3 py-1 rounded-full">● Live - Container Apps</span>
  </div>

  <div class="bg-white rounded-2xl shadow-sm border p-8">
    <h2 class="text-xl font-semibold mb-2">Upload your video</h2>
    <p class="text-gray-500 text-sm mb-6">Extracts 15 clear frames • AI blur detection • 4K supported</p>

    <div id="drop" class="border-2 border-dashed border-gray-200 rounded-xl p-10 text-center hover:border-blue-400 cursor-pointer">
      <div class="text-5xl mb-3">🎬</div>
      <p class="font-medium">Drag & drop video here or click to browse</p>
      <p class="text-xs text-gray-400 mt-1">MP4, MOV up to 200MB</p>
      <input type="file" id="file" accept="video/*" class="hidden">
    </div>

    <div id="status" class="hidden mt-6 p-4 bg-blue-50 rounded-lg text-sm"></div>
    <div id="result" class="hidden mt-6 grid grid-cols-3 gap-3"></div>
  </div>

  <div class="mt-6 grid grid-cols-3 gap-4 text-center text-sm">
    <div class="bg-white p-4 rounded-xl border"><div class="font-bold">OpenCV</div><div class="text-gray-400">Frame Engine</div></div>
    <div class="bg-white p-4 rounded-xl border"><div class="font-bold">Azure Blob</div><div class="text-gray-400">Storage</div></div>
    <div class="bg-white p-4 rounded-xl border"><div class="font-bold">Container Apps</div><div class="text-gray-400">Deployed</div></div>
  </div>
</div>

<script>
const drop = document.getElementById('drop');
const fileInput = document.getElementById('file');
const statusDiv = document.getElementById('status');

drop.onclick = () => fileInput.click();
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('border-blue-400'); };
drop.ondragleave = () => drop.classList.remove('border-blue-400');
drop.ondrop = (e) => { e.preventDefault(); handle(e.dataTransfer.files[0]); };
fileInput.onchange = () => handle(fileInput.files[0]);

async function handle(file){
  if(!file) return;
  statusDiv.classList.remove('hidden');
  statusDiv.innerHTML = `⏳ Uploading ${file.name} and extracting clear frames...`;
  const fd = new FormData(); fd.append('video', file);
  const res = await fetch('/extract', {method:'POST', body: fd});
  const data = await res.json();
  statusDiv.innerHTML = `✅ Done - Extracted ${data.frames} clear frames (blurry removed)`;
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
    return {"status": "ok"}

def is_blurry(image, threshold=100):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold

@app.route("/extract", methods=["POST"])
def extract():
    file = request.files.get("video")
    if not file:
        return jsonify({"error": "no video"}), 400
    tmp_path = f"/tmp/{uuid.uuid4()}.mp4"
    file.save(tmp_path)
    cap = cv2.VideoCapture(tmp_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    count, saved = 0, 0
    output_dir = "/tmp/frames"
    Path(output_dir).mkdir(exist_ok=True)
    for f in Path(output_dir).glob("*.jpg"): f.unlink()

    while True:
        ret, frame = cap.read()
        if not ret: break
        if count % int(fps) == 0:
            if not is_blurry(frame):
                cv2.imwrite(f"{output_dir}/frame_{saved}.jpg", frame)
                saved += 1
        count += 1
        if saved >= 15:
            break

    cap.release()
    os.remove(tmp_path)
    return jsonify({"frames": saved})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)