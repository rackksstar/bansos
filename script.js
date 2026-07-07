const form = document.querySelector("#predictionForm");
const uploadBox = document.querySelector("#uploadBox");
const imageInput = document.querySelector("#imageInput");
const previewImage = document.querySelector("#previewImage");
const statusPill = document.querySelector("#statusPill");
const resultLabel = document.querySelector("#resultLabel");
const resultConfidence = document.querySelector("#resultConfidence");
const confidenceBar = document.querySelector("#confidenceBar");
const predictionTime = document.querySelector("#predictionTime");
const predictionStatus = document.querySelector("#predictionStatus");
const modelName = document.querySelector("#modelName");
const historyList = document.querySelector("#historyList");

let history = [];

function getApiUrl(path) {
  const baseUrl = (window.BANSOS_API_BASE_URL || "").replace(/\/$/, "");
  return `${baseUrl}${path}`;
}

function resetResult(statusText) {
  statusPill.textContent = statusText;
  statusPill.className = "status-pill";
  resultLabel.textContent = "Belum ada hasil";
  resultConfidence.textContent = "0%";
  confidenceBar.style.width = "0%";
  predictionTime.textContent = "-";
  predictionStatus.textContent = "Siap";
  modelName.textContent = "CNN Bansos Classifier";
}

async function predictImage() {
  if (!imageInput.files.length) {
    throw new Error("Silakan upload gambar terlebih dahulu.");
  }

  const formData = new FormData();
  formData.append("image", imageInput.files[0]);

  const response = await fetch(getApiUrl("/predict"), {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Prediksi gagal diproses.");
  }

  return payload;
}

function renderResult(prediction) {
  const time = new Date().toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  statusPill.textContent = "Prediksi selesai";
  statusPill.className = "status-pill done";
  resultLabel.textContent = prediction.label;
  resultConfidence.textContent = `${prediction.confidence}% confidence`;
  confidenceBar.style.width = `${prediction.confidence}%`;
  predictionTime.textContent = time;
  predictionStatus.textContent = "Berhasil";
  if (prediction.model_name) {
    modelName.textContent = prediction.model_name;
  }

  history.unshift(prediction.history || {
    label: prediction.label,
    confidence: prediction.confidence,
    created_at: new Date().toISOString(),
  });
  renderHistory();
}

function renderHistory() {
  historyList.innerHTML = "";

  if (!history.length) {
    const element = document.createElement("li");
    element.textContent = "Belum ada prediksi.";
    historyList.appendChild(element);
    return;
  }

  history.slice(0, 5).forEach((item) => {
    const element = document.createElement("li");
    const date = new Date(item.created_at);
    const time = Number.isNaN(date.getTime())
      ? item.created_at || "-"
      : date.toLocaleString("id-ID", {
          dateStyle: "medium",
          timeStyle: "short",
        });
    element.innerHTML = `<strong>${item.label} - ${item.confidence}%</strong><span>${time}</span>`;
    historyList.appendChild(element);
  });
}

async function loadHistory() {
  try {
    const response = await fetch(getApiUrl("/history"));
    const payload = await response.json();
    if (response.ok) {
      history = payload.history || [];
      renderHistory();
    }
  } catch (error) {
    renderHistory();
  }
}

imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (!file) return;

  previewImage.src = URL.createObjectURL(file);
  uploadBox.classList.add("has-image");
  resetResult("Siap diprediksi");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    statusPill.textContent = "Memproses";
    statusPill.className = "status-pill";
    predictionStatus.textContent = "Memproses";

    const prediction = await predictImage();
    renderResult(prediction);
  } catch (error) {
    statusPill.textContent = "Input kurang";
    statusPill.className = "status-pill error";
    predictionStatus.textContent = error.message;
  }
});

resetResult("Menunggu input");
loadHistory();
