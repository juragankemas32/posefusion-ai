'use strict';

const $ = (id) => document.getElementById(id);
const state = {
  identity: null,
  pose: null,
  previewUrls: { identity: null, pose: null },
  resultUrl: null,
  ready: false,
  busy: false,
};

function setError(message) {
  const box = $('errorBox');
  box.textContent = message;
  box.hidden = !message;
  if (message) box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setStatus(message, tone = '') {
  const box = $('serverStatus');
  box.className = 'server-status' + (tone ? ' ' + tone : '');
  $('statusText').textContent = message;
}

function refreshButton() {
  $('generateBtn').disabled = !state.ready || !state.identity || !state.pose || state.busy;
}

function setPhoto(which, file) {
  if (file && !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    setError('Format foto harus JPG, PNG, atau WEBP.'); return;
  }
  if (file && file.size > 15 * 1024 * 1024) {
    setError('Maksimal ukuran setiap foto adalah 15 MB.'); return;
  }
  setError('');
  if (state.previewUrls[which]) URL.revokeObjectURL(state.previewUrls[which]);
  state[which] = file || null;
  state.previewUrls[which] = file ? URL.createObjectURL(file) : null;
  const present = !!file;
  $(which + 'Empty').hidden = present;
  $(which + 'Preview').hidden = !present;
  $(which + 'Change').hidden = !present;
  $(which + 'Info').hidden = !present;
  $(which + 'Drop').classList.toggle('has-image', present);
  $(which + 'Preview').src = state.previewUrls[which] || '';
  $(which + 'Name').textContent = present ? file.name : '';
  $(which + 'Input').value = '';
  refreshButton();
}

function setupUpload(which) {
  const input = $(which + 'Input');
  const zone = $(which + 'Drop');
  zone.addEventListener('click', () => { if (!state.busy) input.click(); });
  zone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (!state.busy) input.click(); }
  });
  input.addEventListener('change', () => { if (input.files?.[0]) setPhoto(which, input.files[0]); });
  for (const ev of ['dragenter', 'dragover']) zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('dragover'); });
  for (const ev of ['dragleave', 'drop']) zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('dragover'); });
  zone.addEventListener('drop', e => { if (!state.busy && e.dataTransfer.files?.[0]) setPhoto(which, e.dataTransfer.files[0]); });
  $(which + 'Remove').addEventListener('click', () => { if (!state.busy) setPhoto(which, null); });
}

function setBusy(busy) {
  state.busy = busy;
  $('generateText').textContent = busy ? 'Sedang Generate...' : 'Generate Gambar';
  $('buttonSpinner').hidden = !busy;
  $('buttonArrow').hidden = busy;
  $('resultLoading').hidden = !busy;
  if (busy) {
    $('resultPlaceholder').hidden = true;
    $('resultImage').hidden = true;
    $('resultActions').hidden = true;
    $('resultState').textContent = 'MEMPROSES...';
    $('resultState').className = 'result-state';
  }
  refreshButton();
}

function restoreAfterError() {
  if (state.resultUrl) {
    $('resultImage').hidden = false;
    $('resultActions').hidden = false;
    $('resultState').textContent = 'SELESAI';
    $('resultState').className = 'result-state finished';
  } else {
    $('resultPlaceholder').hidden = false;
    $('resultState').textContent = 'BELUM ADA HASIL';
    $('resultState').className = 'result-state';
  }
}

function decodeToUrl(base64, mime = 'image/png') {
  const raw = atob(base64);
  const parts = [];
  for (let offset = 0; offset < raw.length; offset += 65536) {
    const chunk = raw.slice(offset, offset + 65536);
    const bytes = new Uint8Array(chunk.length);
    for (let i = 0; i < chunk.length; i++) bytes[i] = chunk.charCodeAt(i);
    parts.push(bytes);
  }
  return URL.createObjectURL(new Blob(parts, { type: mime }));
}

async function generate() {
  if (!state.identity || !state.pose || !state.ready || state.busy) return;
  setError('');
  if (!$('pinArea').hidden && !$('accessPin').value.trim()) {
    setError('Masukkan PIN akses website terlebih dahulu.'); return;
  }
  setBusy(true);
  const form = new FormData();
  form.append('identity', state.identity);
  form.append('pose', state.pose);
  form.append('aspect', document.querySelector('input[name="aspect"]:checked').value);
  form.append('notes', $('notes').value.trim());
  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: $('pinArea').hidden ? {} : { 'X-App-Pin': $('accessPin').value },
      body: form,
    });
    let data;
    try { data = await response.json(); } catch { throw new Error('Server mengirim respons yang tidak valid.'); }
    if (!response.ok || !data.image) throw new Error(data.error || 'Gagal membuat gambar. Silakan coba lagi.');
    const imageUrl = decodeToUrl(data.image, data.mime);
    if (state.resultUrl) URL.revokeObjectURL(state.resultUrl);
    state.resultUrl = imageUrl;
    $('resultImage').src = imageUrl;
    $('resultImage').hidden = false;
    $('resultActions').hidden = false;
    $('resultPlaceholder').hidden = true;
    $('resultState').textContent = 'SELESAI';
    $('resultState').className = 'result-state finished';
    $('resultCanvas').scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (error) {
    setError(error instanceof TypeError ? 'Tidak dapat menghubungi server. Pastikan website dijalankan melalui Python/hosting, bukan membuka file HTML langsung.' : (error.message || 'Gagal membuat gambar.'));
    restoreAfterError();
  } finally {
    setBusy(false);
  }
}

async function getStatus() {
  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error();
    const data = await response.json();
    state.ready = !!data.ready;
    $('pinArea').hidden = !data.requires_pin;
    if (state.ready) setStatus('AI terhubung • Siap menghasilkan gambar', 'ok');
    else setStatus('API key belum terpasang • Lihat petunjuk di README', 'not-ready');
  } catch {
    state.ready = false;
    setStatus('Backend belum tersambung • Jalankan app.py / deploy website', 'not-ready');
  }
  refreshButton();
}

setupUpload('identity');
setupUpload('pose');
$('notes').addEventListener('input', () => { $('charCounter').textContent = $('notes').value.length + ' / 700'; });
document.querySelectorAll('input[name="aspect"]').forEach(input => {
  input.addEventListener('change', () => {
    document.querySelectorAll('.aspect-option').forEach(el => el.classList.toggle('active', el.querySelector('input').checked));
  });
});
$('generateBtn').addEventListener('click', generate);
$('retryBtn').addEventListener('click', generate);
$('downloadBtn').addEventListener('click', () => {
  if (!state.resultUrl) return;
  const link = document.createElement('a');
  link.href = state.resultUrl;
  link.download = 'PoseFusion-AI-' + new Date().toISOString().replace(/[:.]/g, '-') + '.png';
  document.body.appendChild(link);
  link.click();
  link.remove();
});
getStatus();
