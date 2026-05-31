import os
import io
import zipfile
from flask import Flask, request, send_file, render_template_string, jsonify
from PIL import Image, ImageFile
import pypdf

ImageFile.LOAD_TRUNCATED_IMAGES = True

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>メタデータ削除ツール</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 40px 16px; }
  h1 { font-size: 1.8rem; color: #1a202c; margin-bottom: 8px; }
  .subtitle { color: #718096; margin-bottom: 32px; font-size: 0.95rem; }
  .card { background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); padding: 32px; width: 100%; max-width: 560px; }
  .drop-zone { border: 2px dashed #cbd5e0; border-radius: 12px; padding: 48px 24px; text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 20px; }
  .drop-zone:hover, .drop-zone.drag-over { border-color: #667eea; background: #f7f8ff; }
  .drop-icon { font-size: 2.5rem; margin-bottom: 12px; }
  .drop-text { color: #4a5568; font-size: 0.95rem; }
  .drop-text span { color: #667eea; font-weight: 600; cursor: pointer; }
  .formats { color: #a0aec0; font-size: 0.8rem; margin-top: 8px; }
  #fileInput { display: none; }
  .file-list { margin-bottom: 20px; }
  .file-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: #f7fafc; border-radius: 8px; margin-bottom: 8px; font-size: 0.88rem; }
  .file-name { color: #2d3748; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px; }
  .file-size { color: #a0aec0; font-size: 0.8rem; white-space: nowrap; }
  .remove-btn { background: none; border: none; color: #fc8181; cursor: pointer; font-size: 1.1rem; padding: 0 4px; }
  .btn { width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
  .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
  .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .status { margin-top: 16px; padding: 12px 16px; border-radius: 8px; font-size: 0.9rem; display: none; }
  .status.success { background: #f0fff4; color: #276749; border: 1px solid #9ae6b4; }
  .status.error { background: #fff5f5; color: #c53030; border: 1px solid #feb2b2; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.4); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .info { background: #ebf8ff; border: 1px solid #90cdf4; border-radius: 10px; padding: 16px; margin-bottom: 20px; font-size: 0.85rem; color: #2c5282; }
  .info ul { padding-left: 16px; margin-top: 6px; }
  .info li { margin-top: 4px; }
</style>
</head>
<body>
<h1>メタデータ削除ツール</h1>
<p class="subtitle">JPG / PNG / PDF ファイルから個人情報を含むメタデータを削除</p>
<div class="card">
  <div class="info">
    <strong>削除されるメタデータ</strong>
    <ul>
      <li>撮影日時・カメラ情報（Exif）</li>
      <li>GPS位置情報</li>
      <li>作成者・著作権情報</li>
      <li>ソフトウェア・デバイス情報</li>
    </ul>
  </div>
  <div class="drop-zone" id="dropZone">
    <div class="drop-icon">📂</div>
    <div class="drop-text">ここにファイルをドロップ、または<span onclick="document.getElementById('fileInput').click()">クリックして選択</span></div>
    <div class="formats">対応形式: JPG, PNG, PDF（最大50MB / ファイル）</div>
  </div>
  <input type="file" id="fileInput" multiple accept=".jpg,.jpeg,.png,.pdf">
  <div class="file-list" id="fileList"></div>
  <button class="btn btn-primary" id="processBtn" onclick="processFiles()" disabled>メタデータを削除してダウンロード</button>
  <div class="status" id="status"></div>
</div>
<script>
  let selectedFiles = [];

  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const fileList = document.getElementById('fileList');
  const processBtn = document.getElementById('processBtn');
  const status = document.getElementById('status');

  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles([...e.dataTransfer.files]);
  });
  fileInput.addEventListener('change', () => addFiles([...fileInput.files]));

  function addFiles(files) {
    const allowed = ['image/jpeg', 'image/png', 'application/pdf'];
    files.forEach(f => {
      if (!allowed.includes(f.type) && !f.name.match(/[.](jpg|jpeg|png|pdf)$/i)) return;
      if (!selectedFiles.find(x => x.name === f.name && x.size === f.size)) selectedFiles.push(f);
    });
    renderList();
  }

  function renderList() {
    fileList.innerHTML = selectedFiles.map((f, i) => `
      <div class="file-item">
        <span class="file-name">${f.name}</span>
        <span class="file-size">${(f.size/1024/1024).toFixed(2)} MB</span>
        <button class="remove-btn" onclick="removeFile(${i})">✕</button>
      </div>`).join('');
    processBtn.disabled = selectedFiles.length === 0;
    status.style.display = 'none';
  }

  function removeFile(i) { selectedFiles.splice(i, 1); renderList(); }

  async function processFiles() {
    if (!selectedFiles.length) return;
    processBtn.disabled = true;
    processBtn.innerHTML = '<span class="spinner"></span>処理中...';
    status.style.display = 'none';

    const form = new FormData();
    selectedFiles.forEach(f => form.append('files', f));

    try {
      const res = await fetch('/process', { method: 'POST', body: form });
      if (!res.ok) {
        let msg = '処理に失敗しました';
        try { const err = await res.json(); msg = err.error || msg; } catch {}
        throw new Error(msg);
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename\*?=(?:UTF-8'')?([^;]+)/);
      const filename = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'cleaned.zip';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
      status.textContent = `✓ ${selectedFiles.length}件のファイルを処理しました`;
      status.className = 'status success';
      status.style.display = 'block';
      selectedFiles = []; renderList();
    } catch(e) {
      status.textContent = '❌ ' + e.message;
      status.className = 'status error';
      status.style.display = 'block';
    } finally {
      processBtn.disabled = false;
      processBtn.innerHTML = 'メタデータを削除してダウンロード';
    }
  }
</script>
</body>
</html>"""


@app.route('/')
def index():
    return render_template_string(HTML)


def clean_jpg(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.load()
    out = io.BytesIO()
    # Pillowで再保存するとExif/XMP/IPTC/コメントは引き継がれない
    img.save(out, format='JPEG', quality=95, exif=b'')
    return out.getvalue()


def clean_png(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    out = io.BytesIO()
    # pnginfo=None でtEXt/iTXt/zTXt/tIME等のメタデータチャンクを全て除去
    img.save(out, format='PNG', optimize=True, pnginfo=None)
    return out.getvalue()


def clean_pdf(data: bytes) -> bytes:
    reader = pypdf.PdfReader(io.BytesIO(data))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # 全メタデータ（作成者・所有者・ソフトウェア・日時）を除去
    writer.add_metadata({
        '/Producer': '',
        '/Creator': '',
        '/Author': '',
        '/Title': '',
        '/Subject': '',
        '/Keywords': '',
        '/CreationDate': '',
        '/ModDate': '',
    })
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@app.route('/process', methods=['POST'])
def process():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    results = []
    errors = []

    for f in files:
        name = f.filename or 'file'
        ext = os.path.splitext(name)[1].lower()
        f.stream.seek(0)
        data = f.stream.read()
        try:
            if ext in ('.jpg', '.jpeg'):
                cleaned = clean_jpg(data)
                out_name = os.path.splitext(name)[0] + '_cleaned.jpg'
            elif ext == '.png':
                cleaned = clean_png(data)
                out_name = os.path.splitext(name)[0] + '_cleaned.png'
            elif ext == '.pdf':
                cleaned = clean_pdf(data)
                out_name = os.path.splitext(name)[0] + '_cleaned.pdf'
            else:
                errors.append(f'{name}: 対応していない形式')
                continue
            results.append((out_name, cleaned))
        except Exception as e:
            errors.append(f'{name}: {str(e)}')

    if not results:
        return jsonify({'error': '処理できたファイルがありません: ' + ', '.join(errors)}), 400

    if len(results) == 1:
        out_name, cleaned = results[0]
        return send_file(
            io.BytesIO(cleaned),
            download_name=out_name,
            as_attachment=True,
            mimetype='application/octet-stream'
        )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for out_name, cleaned in results:
            zf.writestr(out_name, cleaned)
    zip_buf.seek(0)
    return send_file(
        zip_buf,
        download_name='cleaned_files.zip',
        as_attachment=True,
        mimetype='application/zip'
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
