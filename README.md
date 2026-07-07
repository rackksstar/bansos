# Bansos Vision

Aplikasi prediksi kelayakan penerima bansos berbasis CNN. Frontend dapat dideploy ke Vercel, backend Python ke Railway, dan file model `.h5` disimpan di Hugging Face.

## Alur Deploy

1. Push project ini ke GitHub.
2. Upload model `models/model_bansos.h5` ke Hugging Face.
3. Deploy backend Python di Railway dari repo GitHub.
4. Set Railway agar mengambil model dari Hugging Face lewat `MODEL_URL`.
5. Deploy frontend di Vercel dari repo GitHub.
6. Masukkan URL backend Railway ke env Vercel `BANSOS_API_BASE_URL`.

## Environment Railway

Set variable berikut di Railway:

```bash
MODEL_URL=https://huggingface.co/<username>/<repo-model>/resolve/main/model_bansos.h5
FRONTEND_ORIGIN=https://<domain-vercel-kamu>.vercel.app
```

Jika model Hugging Face private, tambahkan:

```bash
HF_TOKEN=<token-hugging-face>
```

Railway akan menjalankan backend dengan:

```bash
python app.py
```

Endpoint cek backend:

```text
https://<domain-railway-kamu>.up.railway.app/health
```

## Environment Vercel

Set variable berikut di Vercel:

```bash
BANSOS_API_BASE_URL=https://<domain-railway-kamu>.up.railway.app
```

Setelah mengubah env di Vercel, lakukan redeploy.

## Menjalankan Lokal

Install dependency:

```bash
pip install -r requirements.txt
```

Jalankan server:

```bash
python app.py
```

Buka:

```text
http://127.0.0.1:8000
```
