# PoseFusion AI — Identity & Pose Transfer Website

Website berbahasa Indonesia untuk foto referensi identitas (Foto 1) + pose / scene (Foto 2) → gambar AI yang dapat didownload sebagai PNG. Tampilan responsif untuk HP dan komputer.

**Catatan penting:** Generate benar-benar memanggil OpenAI Images Edit API `gpt-image-1.5`. Dibutuhkan **API key OpenAI dan kredit/billing API** tersendiri. Akun ChatGPT Plus saja tidak otomatis menyediakan kredit API. Tanpa key, web tetap dapat dibuka dan dicoba tampilannya, tetapi **belum dapat menghasilkan foto**.

## Menjalankan di komputer

1. Instal Python 3.10+.
2. Ekstrak ZIP, lalu buka terminal di folder `posefusion-web`.
3. Jalankan:
   ```bash
   python -m venv .venv
   ```
4. Aktifkan virtual environment:
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
5. Instal paket:
   ```bash
   pip install -r requirements.txt
   ```
6. Duplikat `.env.example` menjadi `.env`, lalu isi `OPENAI_API_KEY` dengan kunci milikmu dari https://platform.openai.com/api-keys. Isi juga `APP_ACCESS_PIN` dengan PIN privat.
7. Jalankan server:
   ```bash
   python app.py
   ```
8. Buka **http://localhost:5000**.

Pada HP yang satu Wi-Fi dengan laptop/PC, buka `http://IP-LOKAL-KOMPUTER:5000` (bukan localhost). Komputer harus tetap menyala.

## Cara pakai

1. Upload **Foto 1** (wajah/identitas orang yang ingin dipertahankan).
2. Upload **Foto 2** (pose, arah kepala, tatapan, busana, dan lingkungan yang diinginkan).
3. Biarkan rasio **Otomatis** agar mengikuti foto kedua, atau pilih Portrait/Landscape/Square.
4. Opsional, tulis instruksi tambahan. Jika website dikunci, isi PIN.
5. Klik **Generate Gambar**.
6. Klik **Download PNG** untuk menyimpan hasil.

## Supaya jadi link website online

Bisa deploy ke layanan hosting Python (misalnya Render, Railway, VPS). Jika memakai Render, upload kode ini ke repository GitHub privat, lalu pilih **New → Blueprint** (mendeteksi `render.yaml`) atau **New → Web Service** dan isikan:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 240 app:app`
- Environment variables: `OPENAI_API_KEY`, `APP_ACCESS_PIN`

**Jangan taruh API key dalam HTML/JavaScript atau unggah file `.env` ke GitHub.** Saat dipasang di hosting publik, **wajib buat PIN yang panjang dan rahasia** agar orang lain tidak memakai kredit API milikmu. Sebaiknya aktifkan juga batas pengeluaran di akun API. Untuk penggunaan publik multiuser, tambahkan autentikasi dan rate limiting.

## Catatan kualitas dan privasi

- Foto pertama adalah referensi identitas, foto kedua referensi pose/scene.
- Output PNG resolusi tinggi, tetapi **tidak dijamin 100% identik** dengan wajah, pakaian, sudut, atau latar sumber; model AI dapat menghasilkan variasi.
- Foto dikirim dari server ke layanan OpenAI untuk diproses. Server website tidak menyimpan file input/output secara permanen; foto input diproses dalam folder sementara lalu dihapus setelah panggilan API.
- JPG, PNG, WEBP diterima. Maksimal 15MB per foto dan 30MB per permintaan.
- Gunakan hanya foto yang boleh diproses dan dapatkan persetujuan dari orang dalam foto.

## Dokumentasi API

https://developers.openai.com/api/reference/python/resources/images/methods/edit
