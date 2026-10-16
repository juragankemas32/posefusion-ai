"""PoseFusion AI — private, mobile-friendly image identity & pose transfer studio."""
from __future__ import annotations

import hmac
import os
import tempfile
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # complete upload cap
app.json.ensure_ascii = False

# Keep processing bounds reasonable for memory/host costs.
Image.MAX_IMAGE_PIXELS = 36_000_000
MAX_SINGLE_FILE = 15 * 1024 * 1024
MAX_EDGE = 2400
ASPECT_SIZES = {
    'portrait': '1024x1536',
    'landscape': '1536x1024',
    'square': '1024x1024',
}

# Instruction references the order of the two images sent to the API.
BASE_PROMPT = """
ULTRA-REALISTIC IDENTITY & POSE TRANSFER. Generate ONE cohesive, natural,
photorealistic photograph using exactly two reference images IN THIS ORDER:

IMAGE 1 (first attached image) — IDENTITY REFERENCE ONLY:
The person in Image 1 must be the subject in the final photograph. Preserve that
person's recognizable facial identity: facial structure/proportions, eyes, eyebrows,
nose, lips, jawline, skin tone, hairline, hairstyle, hair texture and natural body
build/proportions. Do not blend identity, face, hairstyle or body with the person
in Image 2. Never retain the original gaze, facial angle or head orientation of
Image 1 when they conflict with Image 2.

IMAGE 2 (second attached image) — TARGET SCENE AND POSE REFERENCE:
Reconstruct the person from Image 1 into the body pose of Image 2. Follow Image 2
as precisely as anatomically possible for head rotation/tilt/pitch, facial
perspective, chin direction, neck orientation, eye direction and exact gaze,
facial expression, torso rotation, shoulder alignment, arm/hand/leg positions,
weight distribution, posture, clothing, accessories, camera angle, crop,
composition, background, lighting, shadows, depth of field and photographic
atmosphere. Outfit should naturally fit the physique of the person from Image 1.

CRITICAL: Reconstruct the head, face, neck, shoulders and body into one continuous,
anatomically correct person. The face of Image 1 must be realistically seen from
the viewing angle in Image 2, NOT pasted over it. Accurate eye perspective and
gaze direction are essential. Preserve realistic skin pores, true skin texture,
natural proportions, matching highlights and scene-specific shadows. The final
result should look like an authentic, unretouched photograph captured directly
in the setting of Image 2.

PRIORITY: (1) Image 1 face/hairstyle identity, (2) Image 1 natural body build,
(3) Image 2 head pose and facial camera angle, (4) Image 2 gaze, (5) Image 2
whole-body pose, (6) Image 2 clothing, (7) Image 2 camera/background/lighting.

AVOID: pasted/transplanted face or head, face-swap appearance, floating head,
frontal face on rotated body, wrong gaze, identity blending, copying Image 2
person's facial identity, disproportionate head, distorted features or limbs,
unnatural neck, mismatched anatomy, asymmetric eyes, wax/plastic skin, unnatural
skin smoothing, visible seams, mismatched lighting, blurry face, artificial look.
Produce the final photograph only. No text, borders, watermarks or comparison layout.
""".strip()


def _json_error(message: str, status: int):
    return jsonify({'error': message}), status


def _prepare_image(file, target: Path):
    """Validate image by decoding it, auto-rotate and save a compact RGB JPEG."""
    data = file.read(MAX_SINGLE_FILE + 1)
    if not data or len(data) > MAX_SINGLE_FILE:
        raise ValueError('Maksimal ukuran setiap foto adalah 15 MB.')
    try:
        with Image.open(BytesIO(data)) as im:
            if im.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValueError('Format foto harus JPG, PNG, atau WEBP.')
            if im.width * im.height > 36_000_000:
                raise ValueError('Resolusi foto terlalu besar (maksimal 36 megapiksel).')
            im.load()
            im = ImageOps.exif_transpose(im)
            dimensions = im.size
            if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                canvas = Image.new('RGB', im.size, (255, 255, 255))
                im = im.convert('RGBA')
                canvas.paste(im, mask=im.getchannel('A'))
                im = canvas
            else:
                im = im.convert('RGB')
            im.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            im.save(target, 'JPEG', quality=94, optimize=True)
            return dimensions
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('File gambar tidak valid atau resolusinya terlalu besar.') from exc


@app.get('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.get('/api/status')
def status():
    return jsonify({
        'ready': bool(os.getenv('OPENAI_API_KEY', '').strip()),
        'requires_pin': bool(os.getenv('APP_ACCESS_PIN', '').strip()),
        'model': 'gpt-image-1.5',
    })


@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return _json_error('Total unggahan terlalu besar. Maksimal 30 MB.', 413)


@app.post('/api/generate')
def generate():
    secret = os.getenv('OPENAI_API_KEY', '').strip()
    if not secret:
        return _json_error('API key belum diatur di server. Lihat README untuk setup.', 503)

    required_pin = os.getenv('APP_ACCESS_PIN', '').strip()
    if required_pin and not hmac.compare_digest(request.headers.get('X-App-Pin', ''), required_pin):
        return _json_error('PIN akses tidak benar.', 401)

    identity = request.files.get('identity')
    pose = request.files.get('pose')
    if not identity or not pose:
        return _json_error('Upload Foto 1 dan Foto 2 terlebih dahulu.', 400)

    aspect = request.form.get('aspect', 'auto')
    if aspect not in ('auto', *ASPECT_SIZES):
        return _json_error('Pilihan rasio tidak tersedia.', 400)

    extra = request.form.get('notes', '').strip()
    if len(extra) > 700:
        return _json_error('Catatan tambahan maksimal 700 karakter.', 400)

    try:
        with tempfile.TemporaryDirectory(prefix='posefusion_') as temp:
            file1 = Path(temp) / '01-identity.jpg'
            file2 = Path(temp) / '02-target-pose.jpg'
            _prepare_image(identity, file1)
            pose_width, pose_height = _prepare_image(pose, file2)

            if aspect == 'auto':
                ratio = pose_width / pose_height
                aspect = 'landscape' if ratio >= 1.15 else ('portrait' if ratio <= .87 else 'square')

            prompt = BASE_PROMPT
            if extra:
                prompt += '\n\nADDITIONAL USER REQUEST (only if it does not override the image-role rules): ' + extra
            prompt += '\n\nRequested output framing: ' + aspect + '.'

            client = OpenAI(api_key=secret, timeout=210, max_retries=1)
            with file1.open('rb') as first, file2.open('rb') as second:
                result = client.images.edit(
                    model='gpt-image-1.5',
                    image=[first, second],
                    prompt=prompt,
                    size=ASPECT_SIZES[aspect],
                    quality='high',
                    input_fidelity='high',
                    output_format='png',
                    n=1,
                )

        if not result.data or not result.data[0].b64_json:
            return _json_error('AI belum mengembalikan gambar. Silakan coba lagi.', 502)
        return jsonify({'image': result.data[0].b64_json, 'mime': 'image/png', 'size': ASPECT_SIZES[aspect]})
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except RateLimitError:
        return _json_error('Batas penggunaan/kredit API tercapai. Periksa akun API.', 429)
    except (APITimeoutError, APIConnectionError):
        return _json_error('Layanan AI tidak merespons. Periksa koneksi server lalu coba lagi.', 504)
    except APIStatusError as exc:
        if exc.status_code == 401:
            return _json_error('API key tidak valid. Periksa konfigurasi server.', 502)
        if exc.status_code in (400, 403):
            return _json_error('Permintaan ditolak layanan AI. Coba foto berbeda atau periksa akses model pada akun API.', 502)
        return _json_error(f'Layanan AI sedang bermasalah (kode {exc.status_code}).', 502)
    except Exception:
        app.logger.exception('Unhandled image generation error')
        return _json_error('Terjadi masalah di server. Periksa log server.', 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=False)
