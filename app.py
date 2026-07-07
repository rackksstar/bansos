from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import cgi
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
from threading import Lock
from urllib.request import Request, urlopen
from uuid import uuid4

import numpy as np
from PIL import Image
import tensorflow as tf


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "models" / "model_bansos.h5"))
HISTORY_PATH = BASE_DIR / "history.json"
UPLOADS_DIR = BASE_DIR / "uploads"
DEFAULT_IMAGE_SIZE = (128, 128)
MODEL_DISPLAY_NAME = "CNN Bansos Classifier"
MODEL_URL = os.getenv("MODEL_URL")
HF_TOKEN = os.getenv("HF_TOKEN")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
CLASS_NAMES = {
    0: "Tidak Layak Menerima Bansos",
    1: "Layak Menerima Bansos",
}
SIGMOID_POSITIVE_CLASS_INDEX = 0

model = None
history_lock = Lock()


def ensure_model_file():
    if MODEL_PATH.exists():
        return

    if not MODEL_URL:
        raise FileNotFoundError(
            f"Model tidak ditemukan: {MODEL_PATH}. Set MODEL_URL dari Hugging Face."
        )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    request = Request(MODEL_URL)
    if HF_TOKEN:
        request.add_header("Authorization", f"Bearer {HF_TOKEN}")

    with urlopen(request) as response, MODEL_PATH.open("wb") as model_file:
        shutil.copyfileobj(response, model_file)


class CompatibleDense(tf.keras.layers.Dense):
    @classmethod
    def from_config(cls, config):
        config = dict(config)
        config.pop("quantization_config", None)
        return super().from_config(config)


def load_prediction_model():
    global model
    if model is None:
        ensure_model_file()
        model = tf.keras.models.load_model(
            MODEL_PATH,
            compile=False,
            custom_objects={"Dense": CompatibleDense},
        )
    return model


def get_model_image_size(prediction_model):
    input_shape = prediction_model.input_shape
    if isinstance(input_shape, list):
        input_shape = input_shape[0]

    if len(input_shape) >= 4 and input_shape[1] and input_shape[2]:
        return int(input_shape[2]), int(input_shape[1])

    return DEFAULT_IMAGE_SIZE


def model_has_preprocessing_layer(prediction_model):
    preprocessing_layers = {"Rescaling", "Normalization"}
    layers_to_check = list(prediction_model.layers[:5])

    for layer in prediction_model.layers[:2]:
        inner_layers = getattr(layer, "layers", None)
        if inner_layers:
            layers_to_check.extend(inner_layers[:5])

    return any(layer.__class__.__name__ in preprocessing_layers for layer in layers_to_check)


def preprocess_image(image_source):
    prediction_model = load_prediction_model()
    image_size = get_model_image_size(prediction_model)
    image = Image.open(image_source).convert("RGB")
    image = image.resize(image_size)
    image_array = np.asarray(image, dtype=np.float32)
    if not model_has_preprocessing_layer(prediction_model):
        image_array = image_array / 255.0
    return np.expand_dims(image_array, axis=0)


def predict_bansos(image_source):
    prediction_model = load_prediction_model()
    image_array = preprocess_image(image_source)
    raw_prediction = prediction_model.predict(image_array, verbose=0)
    positive_probability = float(np.ravel(raw_prediction)[0])
    negative_probability = 1 - positive_probability
    class_index = (
        SIGMOID_POSITIVE_CLASS_INDEX
        if positive_probability > 0.5
        else 1 - SIGMOID_POSITIVE_CLASS_INDEX
    )

    confidence = (
        positive_probability
        if class_index == SIGMOID_POSITIVE_CLASS_INDEX
        else negative_probability
    )
    probability_layak = (
        positive_probability
        if SIGMOID_POSITIVE_CLASS_INDEX == 1
        else negative_probability
    )
    return {
        "label": CLASS_NAMES[class_index],
        "confidence": round(confidence * 100, 2),
        "probability_layak": round(probability_layak * 100, 2),
        "class_index": class_index,
        "model_name": MODEL_DISPLAY_NAME,
    }


def save_uploaded_image(file_item):
    UPLOADS_DIR.mkdir(exist_ok=True)
    original_name = Path(file_item.filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", original_name).strip(".-")
    if not safe_name:
        safe_name = "foto-rumah.jpg"

    image_name = f"{uuid4().hex}-{safe_name}"
    image_path = UPLOADS_DIR / image_name
    file_item.file.seek(0)
    with image_path.open("wb") as image_file:
        shutil.copyfileobj(file_item.file, image_file)

    return image_path, f"uploads/{image_name}"


def read_history():
    if not HISTORY_PATH.exists():
        return []

    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as history_file:
            data = json.load(history_file)
    except (json.JSONDecodeError, OSError):
        return []

    return data if isinstance(data, list) else []


def save_history_entry(result, filename, image_url):
    entry = {
        "id": uuid4().hex,
        "filename": filename,
        "image_url": image_url,
        "label": result["label"],
        "confidence": result["confidence"],
        "probability_layak": result["probability_layak"],
        "class_index": result["class_index"],
        "model_name": result["model_name"],
        "is_correct": None,
        "reviewed_at": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    with history_lock:
        history = read_history()
        history.insert(0, entry)
        with HISTORY_PATH.open("w", encoding="utf-8") as history_file:
            json.dump(history, history_file, ensure_ascii=False, indent=2)

    return entry


def update_history_validation(history_id, index, is_correct):
    with history_lock:
        history = read_history()
        target = None

        if history_id:
            target = next((item for item in history if item.get("id") == history_id), None)
        elif isinstance(index, int) and 0 <= index < len(history):
            target = history[index]

        if target is None:
            return None

        if "id" not in target:
            target["id"] = uuid4().hex
        target["is_correct"] = bool(is_correct)
        target["reviewed_at"] = datetime.now().isoformat(timespec="seconds")

        with HISTORY_PATH.open("w", encoding="utf-8") as history_file:
            json.dump(history, history_file, ensure_ascii=False, indent=2)

    return target


class BansosHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_POST(self):
        if self.path == "/history/validate":
            self.handle_history_validation()
            return

        if self.path != "/predict":
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint tidak ditemukan")
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json(
                {"error": "Request harus berupa multipart/form-data."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                },
            )
            file_item = form["image"] if "image" in form else None
            if file_item is None or not getattr(file_item, "filename", ""):
                self.send_json(
                    {"error": "Silakan upload foto rumah terlebih dahulu."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            image_path, image_url = save_uploaded_image(file_item)
            result = predict_bansos(image_path)
            result["history"] = save_history_entry(result, file_item.filename, image_url)
            self.send_json(result)
        except Exception as error:
            self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_history_validation(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            self.send_json(
                {"error": "Request harus berupa application/json."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if "is_correct" not in payload:
                self.send_json(
                    {"error": "Status benar/salah belum dikirim."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            updated = update_history_validation(
                payload.get("id"),
                payload.get("index"),
                payload["is_correct"],
            )
            if updated is None:
                self.send_json(
                    {"error": "Riwayat tidak ditemukan."},
                    HTTPStatus.NOT_FOUND,
                )
                return

            self.send_json({"history": read_history(), "updated": updated})
        except (json.JSONDecodeError, ValueError):
            self.send_json(
                {"error": "Data validasi tidak valid."},
                HTTPStatus.BAD_REQUEST,
            )
        except Exception as error:
            self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_GET(self):
        if self.path == "/health":
            self.send_json({"status": "ok", "model_loaded": model is not None})
            return

        if self.path == "/history":
            self.send_json({"history": read_history()})
            return

        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", FRONTEND_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, payload, status=HTTPStatus.OK):
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def main():
    port = int(os.getenv("PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))
    load_prediction_model()
    server = ThreadingHTTPServer(("0.0.0.0", port), BansosHandler)
    print(f"Server berjalan di http://0.0.0.0:{port}")
    print("Tekan Ctrl+C untuk menghentikan server.")
    server.serve_forever()


if __name__ == "__main__":
    main()
