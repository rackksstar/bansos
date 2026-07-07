const historyTableBody = document.querySelector("#historyTableBody");
const historyCount = document.querySelector("#historyCount");
const accuracyPercent = document.querySelector("#accuracyPercent");
const accuracyBar = document.querySelector("#accuracyBar");
const accuracySummary = document.querySelector("#accuracySummary");

let currentHistory = [];

function getApiUrl(path) {
  const baseUrl = (window.BANSOS_API_BASE_URL || "").replace(/\/$/, "");
  return `${baseUrl}${path}`;
}

function getAssetUrl(path) {
  if (!path || /^https?:\/\//i.test(path)) return path;
  return getApiUrl(`/${path.replace(/^\//, "")}`);
}

function formatDateTime(value) {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatValidationStatus(value) {
  if (value === true) return "Benar";
  if (value === false) return "Salah";
  return "Belum dinilai";
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch (error) {
    return {
      error: response.ok
        ? "Response server tidak valid."
        : "Endpoint validasi belum aktif. Restart server Python terlebih dahulu.",
    };
  }
}

function showHistoryError(message) {
  historyCount.textContent = "Gagal";
  historyCount.classList.add("error");
  accuracySummary.textContent = message;
}

function renderAccuracy(history) {
  const reviewed = history.filter((item) => typeof item.is_correct === "boolean");
  const correct = reviewed.filter((item) => item.is_correct).length;
  const percent = reviewed.length ? Math.round((correct / reviewed.length) * 100) : 0;

  accuracyPercent.textContent = `${percent}%`;
  accuracyBar.style.width = `${percent}%`;

  if (!reviewed.length) {
    accuracySummary.textContent = "Belum ada prediksi yang dinilai.";
    return;
  }

  accuracySummary.textContent = `${correct} dari ${reviewed.length} prediksi yang dinilai sudah benar.`;
}

function appendTextCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
}

function appendResultCell(row, value) {
  const cell = document.createElement("td");
  const strong = document.createElement("strong");
  strong.textContent = value;
  cell.appendChild(strong);
  row.appendChild(cell);
}

function appendImageCell(row, item) {
  const cell = document.createElement("td");
  if (item.image_url) {
    const image = document.createElement("img");
    image.className = "history-thumbnail";
    image.src = getAssetUrl(item.image_url);
    image.alt = item.filename || "Foto input prediksi";
    cell.appendChild(image);
  } else {
    cell.textContent = "Belum tersimpan";
    cell.className = "muted-cell";
  }
  row.appendChild(cell);
}

function appendActionCell(row, item, index) {
  const cell = document.createElement("td");
  const actions = document.createElement("div");
  actions.className = "validation-actions";

  [
    { label: "Benar", value: true },
    { label: "Salah", value: false },
  ].forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "validation-button";
    button.textContent = action.label;
    button.disabled = item.is_correct === action.value;
    button.addEventListener("click", async () => {
      try {
        await updateValidation(item, index, action.value);
      } catch (error) {
        showHistoryError(error.message);
      }
    });
    actions.appendChild(button);
  });

  cell.appendChild(actions);
  row.appendChild(cell);
}

function renderHistory(history) {
  currentHistory = history;
  historyTableBody.innerHTML = "";
  historyCount.textContent = `${history.length} data`;
  historyCount.classList.remove("error");
  renderAccuracy(history);

  if (!history.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="8">Belum ada riwayat prediksi.</td>';
    historyTableBody.appendChild(row);
    return;
  }

  history.forEach((item, index) => {
    const row = document.createElement("tr");
    appendTextCell(row, formatDateTime(item.created_at));
    appendImageCell(row, item);
    appendTextCell(row, item.filename || "-");
    appendResultCell(row, item.label || "-");
    appendTextCell(row, `${item.confidence ?? "-"}%`);
    appendTextCell(row, formatValidationStatus(item.is_correct));
    appendActionCell(row, item, index);
    appendTextCell(row, item.model_name || "-");
    historyTableBody.appendChild(row);
  });
}

async function updateValidation(item, index, isCorrect) {
  const response = await fetch(getApiUrl("/history/validate"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      id: item.id,
      index,
      is_correct: isCorrect,
    }),
  });
  const payload = await readJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.error || "Validasi gagal disimpan.");
  }

  renderHistory(payload.history || currentHistory);
}

async function loadHistory() {
  try {
    const response = await fetch(getApiUrl("/history"));
    const payload = await readJsonResponse(response);

    if (!response.ok) {
      throw new Error(payload.error || "Riwayat gagal dimuat.");
    }

    renderHistory(payload.history || []);
  } catch (error) {
    showHistoryError(error.message);
    historyTableBody.innerHTML = `<tr><td colspan="8">${error.message}</td></tr>`;
  }
}

loadHistory();
