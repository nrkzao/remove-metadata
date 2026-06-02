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
  .file-item { background: #f7fafc; border-radius: 8px; margin-bottom: 8px; font-size: 0.88rem; overflow: hidden; }
  .file-item-top { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px 6px; }
  .file-item-bottom { display: flex; align-items: center; padding: 0 14px 10px; gap: 6px; }
  .file-name { color: #2d3748; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px; }
  .file-size { color: #a0aec0; font-size: 0.8rem; white-space: nowrap; }
  .remove-btn { background: none; border: none; color: #fc8181; cursor: pointer; font-size: 1.1rem; padding: 0 4px; }
  .rename-label { color: #718096; font-size: 0.78rem; white-space: nowrap; }
  .rename-input { flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px 8px; font-size: 0.82rem; color: #2d3748; outline: none; }
  .rename-input:focus { border-color: #667eea; }
  .rename-ext { color: #a0aec0; font-size: 0.82rem; white-space: nowrap; }
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
  let customNames = {};

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
      if (!selectedFiles.find(x => x.name === f.name && x.size === f.size)) {
        selectedFiles.push(f);
        const base = f.name.replace(/\.[^.]+$/, '');
        customNames[f.name] = base;
      }
    });
    renderList();
  }

  function getExt(name) { return name.match(/(\.[^.]+)$/)?.[1] || ''; }

  function renderList() {
    fileList.innerHTML = selectedFiles.map((f, i) => {
      const ext = getExt(f.name);
      const val = customNames[f.name] || f.name.replace(/\.[^.]+$/, '');
      return `
      <div class="file-item">
        <div class="file-item-top">
          <span class="file-name">${f.name}</span>
          <span class="file-size">${(f.size/1024/1024).toFixed(2)} MB</span>
          <button class="remove-btn" onclick="removeFile(${i})">✕</button>
        </div>
        <div class="file-item-bottom">
          <span class="rename-label">保存名:</span>
          <input class="rename-input" type="text" value="${val}" oninput="customNames['${f.name}']=this.value" placeholder="ファイル名（拡張子不要）">
          <span class="rename-ext">${ext}</span>
        </div>
      </div>`;
    }).join('');
    processBtn.disabled = selectedFiles.length === 0;
    status.style.display = 'none';
  }

  function removeFile(i) {
    delete customNames[selectedFiles[i].name];
    selectedFiles.splice(i, 1);
    renderList();
  }

  async function processFiles() {
    if (!selectedFiles.length) return;
    processBtn.disabled = true;
    processBtn.innerHTML = '<span class="spinner"></span>処理中...';
    status.style.display = 'none';

    const form = new FormData();
    selectedFiles.forEach(f => {
      form.append('files', f);
      const ext = getExt(f.name);
      const base = (customNames[f.name] || f.name.replace(/\.[^.]+$/, '')).trim() || f.name.replace(/\.[^.]+$/, '');
      form.append('names', base + ext);
    });

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
    """JPEGバイナリを直接操作してメタデータセグメントを除去（再圧縮なし）"""
    if len(data) < 4 or data[:2] != b'\xff\xd8':
        raise ValueError('JPEGファイルではありません')

    out = bytearray(b'\xff\xd8')
    i = 2

    while i < len(data):
        # 0xff を探す
        if data[i] != 0xff:
            # SOS以降の生データ（ここに来るのは構造が壊れている場合のみ）
            out.extend(data[i:])
            break

        # 連続する 0xff をスキップ（パディング）
        while i < len(data) and data[i] == 0xff:
            i += 1
        if i >= len(data):
            break

        marker = data[i]
        i += 1

        # EOI（画像終端）
        if marker == 0xd9:
            out.extend(b'\xff\xd9')
            break

        # RST0-RST7（長さフィールドなし）
        if 0xd0 <= marker <= 0xd7:
            out.extend(bytes([0xff, marker]))
            continue

        # 長さフィールドを読む
        if i + 2 > len(data):
            break
        seg_len = int.from_bytes(data[i:i+2], 'big')
        seg_end = i + seg_len
        seg_data = data[i:seg_end]
        i = seg_end

        # SOS（Start of Scan）: ヘッダの後は生の圧縮データ → 残り全部を追記して終了
        if marker == 0xda:
            out.extend(b'\xff\xda')
            out.extend(seg_data)
            out.extend(data[i:])
            break

        # 削除対象: APP1〜APP15（Exif/XMP/IPTC等）、COM（コメント）
        if (0xe1 <= marker <= 0xef) or marker == 0xfe:
            continue  # スキップ

        # それ以外（APP0/JFIF、SOF、DHT、DQT 等）は保持
        out.extend(bytes([0xff, marker]))
        out.extend(seg_data)

    return bytes(out)


def clean_png(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.load()
    out = io.BytesIO()
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
    custom_names = request.form.getlist('names')
    if not files:
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    results = []
    errors = []

    for idx, f in enumerate(files):
        name = f.filename or 'file'
        ext = os.path.splitext(name)[1].lower()
        # クライアント指定の保存名があれば使用、なければ元のファイル名を使用
        if idx < len(custom_names) and custom_names[idx].strip():
            out_base = os.path.splitext(custom_names[idx])[0]
        else:
            out_base = os.path.splitext(name)[0]
        f.stream.seek(0)
        data = f.stream.read()
        try:
            if ext in ('.jpg', '.jpeg'):
                cleaned = clean_jpg(data)
                out_name = out_base + '.jpg'
            elif ext == '.png':
                cleaned = clean_png(data)
                out_name = out_base + '.png'
            elif ext == '.pdf':
                cleaned = clean_pdf(data)
                out_name = out_base + '.pdf'
            else:
                errors.append(f'{name}: 対応していない形式')
                continue
            results.append((out_name, cleaned))
        except Exception as e:
            import traceback
            errors.append(f'{name}: {str(e)} ({traceback.format_exc()[-200:]})')

    if not results:
        return jsonify({'error': '処理できたファイルがありません: ' + ' / '.join(errors)}), 400

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
