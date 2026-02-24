const $ = (id) => document.getElementById(id);

const els = {
  sourceMode: $("sourceMode"),
  provider: $("provider"),
  uploadField: $("uploadField"),
  pathField: $("pathField"),
  fileInput: $("fileInput"),
  filePath: $("filePath"),
  modelTextField: $("modelTextField"),
  modelName: $("modelName"),
  openrouterModelField: $("openrouterModelField"),
  openrouterModelSearch: $("openrouterModelSearch"),
  openrouterModelSelect: $("openrouterModelSelect"),
  btnReloadOpenrouterModels: $("btnReloadOpenrouterModels"),
  openrouterModelsHint: $("openrouterModelsHint"),
  apiKey: $("apiKey"),
  baseUrl: $("baseUrl"),
  inputColumns: $("inputColumns"),
  inputTemplate: $("inputTemplate"),
  sheetName: $("sheetName"),
  modelColumn: $("modelColumn"),
  instructionMode: $("instructionMode"),
  instructionColumn: $("instructionColumn"),
  fixedInstruction: $("fixedInstruction"),
  systemPrompt: $("systemPrompt"),
  userTemplate: $("userTemplate"),
  splitMode: $("splitMode"),
  delimiter: $("delimiter"),
  outputColumns: $("outputColumns"),
  outputFileName: $("outputFileName"),
  targetSheetName: $("targetSheetName"),
  targetStartRow: $("targetStartRow"),
  targetStartColumn: $("targetStartColumn"),
  writeHeaders: $("writeHeaders"),
  exportColumns: $("exportColumns"),
  globalConcurrency: $("globalConcurrency"),
  providerConcurrency: $("providerConcurrency"),
  temperature: $("temperature"),
  retries: $("retries"),
  startRow: $("startRow"),
  endRow: $("endRow"),
  skipCompleted: $("skipCompleted"),
  strictParse: $("strictParse"),
  statusColumn: $("statusColumn"),
  errorColumn: $("errorColumn"),
  rawOutputColumn: $("rawOutputColumn"),
  configPreview: $("configPreview"),
  flashMessage: $("flashMessage"),
  jobIdInput: $("jobIdInput"),
  jobSummary: $("jobSummary"),
  jobsList: $("jobsList"),
  btnRun: $("btnRun"),
  btnRefreshJob: $("btnRefreshJob"),
  btnPollToggle: $("btnPollToggle"),
  btnDownloadJob: $("btnDownloadJob"),
  btnLoadJobs: $("btnLoadJobs"),
  btnLoadJobsTop: $("btnLoadJobsTop"),
  applyMockPreset: $("applyMockPreset"),
  applyOpenRouterPreset: $("applyOpenRouterPreset"),
};

let pollTimer = null;
let latestJobId = "";
let openrouterModelsCache = [];
let openrouterModelsLoaded = false;

function parseCsvList(value) {
  return (value || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function numOrUndefined(value) {
  if (value === "" || value === null || value === undefined) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function setFlash(text, kind = "neutral") {
  els.flashMessage.textContent = text;
  els.flashMessage.className = `flash ${kind}`;
}

function toggleSourceMode() {
  const mode = els.sourceMode.value;
  els.uploadField.classList.toggle("hidden", mode !== "upload");
  els.pathField.classList.toggle("hidden", mode !== "path");
}

function selectedModelValue() {
  if (els.provider.value === "openrouter" && !els.openrouterModelField.classList.contains("hidden")) {
    return (els.openrouterModelSelect.value || "").trim();
  }
  return (els.modelName.value || "").trim();
}

function buildConfig() {
  const inputColumns = parseCsvList(els.inputColumns.value);
  const outputColumns = parseCsvList(els.outputColumns.value);
  const exportColumns = parseCsvList(els.exportColumns.value);
  const inputTemplate = els.inputTemplate.value.trim();
  const cfg = {
    input: {
      input_columns: inputColumns,
    },
    prompt: {
      instruction_mode: els.instructionMode.value,
      user_template: els.userTemplate.value,
    },
    model: {
      provider: els.provider.value,
      model: selectedModelValue(),
      retries: numOrUndefined(els.retries.value) ?? 2,
    },
    concurrency: {
      global_concurrency: numOrUndefined(els.globalConcurrency.value) ?? 10,
      provider_concurrency: numOrUndefined(els.providerConcurrency.value) ?? 10,
    },
    rows: {
      status_column: els.statusColumn.value.trim() || "status",
      error_column: els.errorColumn.value.trim() || "error",
      raw_output_column: els.rawOutputColumn.value.trim() || "output_raw",
      skip_completed: els.skipCompleted.checked,
    },
    output: {
      split_mode: els.splitMode.value,
      strict_parse: els.strictParse.checked,
    },
  };

  if (inputTemplate) cfg.input.input_template = inputTemplate;
  if (!inputTemplate && inputColumns.length === 0) cfg.input.input_columns = ["text"];

  const instructionColumn = els.instructionColumn.value.trim();
  const fixedInstruction = els.fixedInstruction.value.trim();
  const systemPrompt = els.systemPrompt.value.trim();

  if (instructionColumn) cfg.prompt.instruction_column = instructionColumn;
  if (fixedInstruction) cfg.prompt.fixed_instruction = fixedInstruction;
  if (systemPrompt) cfg.prompt.system_prompt = systemPrompt;

  const apiKey = els.apiKey.value.trim();
  const baseUrl = els.baseUrl.value.trim();
  const modelColumn = els.modelColumn.value.trim();
  const sheetName = els.sheetName.value.trim();

  if (apiKey) cfg.model.api_key = apiKey;
  if (baseUrl) cfg.model.base_url = baseUrl;
  if (modelColumn) cfg.model.model_column = modelColumn;
  if (sheetName) cfg.rows.sheet_name = sheetName;

  const temperature = numOrUndefined(els.temperature.value);
  if (temperature !== undefined) cfg.model.temperature = temperature;

  const startRow = numOrUndefined(els.startRow.value);
  const endRow = numOrUndefined(els.endRow.value);
  if (startRow !== undefined) cfg.rows.start_row = startRow;
  if (endRow !== undefined) cfg.rows.end_row = endRow;

  if (els.splitMode.value === "delimiter") {
    cfg.output.delimiter = els.delimiter.value || "||";
  }
  if (outputColumns.length > 0) {
    cfg.output.output_columns = outputColumns;
  }

  const outputFileName = els.outputFileName.value.trim();
  const targetSheetName = els.targetSheetName.value.trim();
  const targetStartColumn = els.targetStartColumn.value.trim();
  const targetStartRow = numOrUndefined(els.targetStartRow.value);
  if (outputFileName) cfg.output.output_file_name = outputFileName;
  if (targetSheetName) cfg.output.target_sheet_name = targetSheetName;
  if (targetStartColumn) cfg.output.target_start_column = targetStartColumn;
  if (targetStartRow !== undefined) cfg.output.target_start_row = targetStartRow;
  cfg.output.write_headers = els.writeHeaders.checked;
  if (exportColumns.length > 0) cfg.output.export_columns = exportColumns;

  return cfg;
}

function formatOpenrouterOptionLabel(model) {
  const ctx = model.context_length ? ` • سياق ${Number(model.context_length).toLocaleString("en-US")}` : "";
  const name = model.name && model.name !== model.id ? ` — ${model.name}` : "";
  return `${model.id}${name}${ctx}`;
}

function populateOpenrouterSelect(models, preserveValue) {
  els.openrouterModelSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = models.length ? "اختر نموذجًا من OpenRouter" : "لا توجد نماذج متاحة";
  els.openrouterModelSelect.appendChild(placeholder);

  models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = formatOpenrouterOptionLabel(model);
    option.dataset.searchText = `${model.id} ${model.name || ""} ${model.description || ""}`.toLowerCase();
    els.openrouterModelSelect.appendChild(option);
  });

  if (preserveValue) {
    els.openrouterModelSelect.value = preserveValue;
  }
  if (!els.openrouterModelSelect.value && models.length) {
    els.openrouterModelSelect.selectedIndex = 1;
  }
  if (els.openrouterModelSelect.value) {
    els.modelName.value = els.openrouterModelSelect.value;
  }
}

function applyOpenrouterFilter() {
  const q = (els.openrouterModelSearch.value || "").trim().toLowerCase();
  const currentValue = els.openrouterModelSelect.value || els.modelName.value || "";
  const filtered = !q
    ? openrouterModelsCache
    : openrouterModelsCache.filter((m) => {
        const hay = `${m.id} ${m.name || ""} ${m.description || ""}`.toLowerCase();
        return hay.includes(q);
      });
  populateOpenrouterSelect(filtered, currentValue);
  els.openrouterModelsHint.textContent = `عدد النماذج المعروضة: ${filtered.length} من أصل ${openrouterModelsCache.length}`;
}

async function loadOpenrouterModels(force = false) {
  if (openrouterModelsLoaded && !force) {
    applyOpenrouterFilter();
    return;
  }
  els.btnReloadOpenrouterModels.disabled = true;
  els.openrouterModelsHint.textContent = "جاري تحميل النماذج من OpenRouter...";
  try {
    const url = force ? "/providers/openrouter/models?force_refresh=true" : "/providers/openrouter/models";
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر تحميل نماذج OpenRouter");
    openrouterModelsCache = Array.isArray(data.models) ? data.models : [];
    openrouterModelsLoaded = true;
    applyOpenrouterFilter();
    const sourceText = data.source === "cache" ? "من الكاش المحلي" : "من OpenRouter";
    els.openrouterModelsHint.textContent = `تم تحميل ${openrouterModelsCache.length} نموذج (${sourceText})`;
    setFlash(`تم تحميل ${openrouterModelsCache.length} نموذج من OpenRouter`, "ok");
  } catch (err) {
    els.openrouterModelsHint.textContent = `تعذر التحميل: ${err.message || err}`;
    setFlash(`تعذّر تحميل قائمة OpenRouter: ${err.message || err}`, "error");
  } finally {
    els.btnReloadOpenrouterModels.disabled = false;
    refreshConfigPreview();
  }
}

async function handleProviderChange() {
  const isOpenrouter = els.provider.value === "openrouter";
  els.modelTextField.classList.toggle("hidden", isOpenrouter);
  els.openrouterModelField.classList.toggle("hidden", !isOpenrouter);

  if (els.provider.value === "mock") {
    els.modelName.value = els.modelName.value || "mock-1";
  }

  if (isOpenrouter) {
    await loadOpenrouterModels(false);
  }
  refreshConfigPreview();
}

function refreshConfigPreview() {
  try {
    const cfg = buildConfig();
    els.configPreview.value = JSON.stringify(cfg, null, 2);
  } catch (err) {
    els.configPreview.value = `خطأ في بناء الإعدادات: ${err}`;
  }
}

function applyMockPreset() {
  els.provider.value = "mock";
  els.modelName.value = "mock-1";
  els.instructionMode.value = "per_row";
  els.instructionColumn.value = "instructions";
  els.fixedInstruction.value = "";
  els.systemPrompt.value = "";
  els.inputColumns.value = "text";
  els.splitMode.value = "json";
  els.outputColumns.value = "";
  els.userTemplate.value = "{instruction}\n\nالبيانات:\n{input}\n\nأعد الإخراج JSON فقط.";
  handleProviderChange();
  refreshConfigPreview();
  setFlash("تم تطبيق قالب Mock للتجربة السريعة", "ok");
}

function applyOpenRouterPreset() {
  els.provider.value = "openrouter";
  els.modelName.value = "openai/gpt-4.1-mini";
  els.instructionMode.value = "fixed";
  els.fixedInstruction.value = "حلل النص وأعد JSON فقط بالمفاتيح: summary, sentiment, topic, priority";
  els.systemPrompt.value = "أنت محلل بيانات أعمال. لا تضف أي شرح خارج JSON.";
  els.inputColumns.value = "text";
  els.splitMode.value = "json";
  els.outputColumns.value = "summary,sentiment,topic,priority";
  els.userTemplate.value = "{instruction}\n\nالبيانات:\n{input}";
  handleProviderChange().then(() => {
    if (openrouterModelsLoaded) {
      els.openrouterModelSelect.value = "openai/gpt-4.1-mini";
      if (els.openrouterModelSelect.value) {
        els.modelName.value = els.openrouterModelSelect.value;
      }
      refreshConfigPreview();
    }
  });
  refreshConfigPreview();
  setFlash("تم تطبيق قالب OpenRouter. تأكد من وضع OPENROUTER_API_KEY في .env", "ok");
}

async function runJob() {
  refreshConfigPreview();
  const config = buildConfig();
  const mode = els.sourceMode.value;

  els.btnRun.disabled = true;
  setFlash("جاري إرسال المهمة...", "neutral");
  try {
    let response;
    if (mode === "upload") {
      const file = els.fileInput.files[0];
      if (!file) throw new Error("اختر ملفًا أولًا");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("config_json", JSON.stringify(config));
      response = await fetch("/jobs/run-file", {
        method: "POST",
        body: formData,
      });
    } else {
      const filePath = els.filePath.value.trim();
      if (!filePath) throw new Error("أدخل مسار الملف");
      response = await fetch("/jobs/run-path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath, config }),
      });
    }

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "فشل إنشاء المهمة");
    const job = data.job;
    latestJobId = job.id;
    els.jobIdInput.value = job.id;
    setFlash(`تم إنشاء المهمة بنجاح: ${job.id}`, "ok");
    renderJobSummary(job);
    await loadJobs();
  } catch (err) {
    setFlash(`تعذّر التشغيل: ${err.message || err}`, "error");
  } finally {
    els.btnRun.disabled = false;
  }
}

function stateBadge(state) {
  const iconMap = {
    queued: "🕒",
    running: "🏃",
    completed: "✅",
    failed: "❌",
    cancelled: "⛔",
  };
  const icon = iconMap[state] || "•";
  return `<span class="badge ${state}">${icon} ${state}</span>`;
}

function renderJobSummary(job) {
  const p = job.progress || {};
  const rows = [
    ["حالة المهمة", stateBadge(job.state)],
    ["رقم المهمة", `<code>${job.id}</code>`],
    ["الملف المصدر", job.source_file || "-"],
    ["الملف الناتج", job.output_file || "-"],
    ["إجمالي الصفوف", p.total_rows ?? 0],
    ["مكتملة", p.completed_rows ?? 0],
    ["فاشلة", p.failed_rows ?? 0],
    ["قيد التنفيذ", p.running_rows ?? 0],
    ["بالانتظار", p.queued_rows ?? 0],
    ["متخطاة", p.skipped_rows ?? 0],
  ];

  let html = `<div class="summary-grid">`;
  for (const [k, v] of rows) {
    html += `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`;
  }
  html += `</div>`;

  if (job.error) {
    html += `<div class="flash error" style="margin-top:10px;">خطأ المهمة: ${escapeHtml(job.error)}</div>`;
  }

  if (Array.isArray(job.rows) && job.rows.length > 0) {
    const sample = job.rows.slice(-5);
    html += `<div style="margin-top:12px;font-weight:700;">🧪 آخر صفوف المعالجة (آخر 5)</div>`;
    html += `<pre class="codebox">${escapeHtml(JSON.stringify(sample, null, 2))}</pre>`;
  }

  els.jobSummary.innerHTML = html;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function getJob(jobId) {
  const response = await fetch(`/jobs/${encodeURIComponent(jobId)}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "تعذّر جلب المهمة");
  return data.job;
}

async function refreshSelectedJob() {
  const jobId = (els.jobIdInput.value || latestJobId).trim();
  if (!jobId) {
    setFlash("أدخل رقم المهمة أو شغّل مهمة أولًا", "error");
    return;
  }
  try {
    const job = await getJob(jobId);
    latestJobId = job.id;
    els.jobIdInput.value = job.id;
    renderJobSummary(job);
    setFlash(`تم تحديث المهمة: ${job.id}`, "neutral");
    if (["completed", "failed", "cancelled"].includes(job.state)) {
      stopPolling();
    }
  } catch (err) {
    setFlash(`تعذّر تحديث المهمة: ${err.message || err}`, "error");
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    refreshSelectedJob().catch(() => {});
  }, 2500);
  els.btnPollToggle.textContent = "⏹️ إيقاف المراقبة";
  setFlash("تم بدء المراقبة كل 2.5 ثانية", "neutral");
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  els.btnPollToggle.textContent = "⏱️ بدء المراقبة";
}

function togglePolling() {
  if (pollTimer) stopPolling();
  else startPolling();
}

async function loadJobs() {
  try {
    const response = await fetch("/jobs");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "فشل تحميل المهام");
    renderJobsList(data.jobs || []);
  } catch (err) {
    els.jobsList.innerHTML = `<div class="empty-state">تعذّر تحميل المهام: ${escapeHtml(err.message || err)}</div>`;
  }
}

function renderJobsList(jobs) {
  if (!jobs.length) {
    els.jobsList.innerHTML = `<div class="empty-state">لا توجد مهام بعد.</div>`;
    return;
  }

  els.jobsList.innerHTML = jobs
    .map((job) => {
      const p = job.progress || {};
      return `
        <div class="job-card">
          <div class="head">
            <div class="job-id">${job.id}</div>
            ${stateBadge(job.state)}
          </div>
          <div class="meta">
            <div>📄 المصدر: ${escapeHtml(job.source_file || "-")}</div>
            <div>📤 الناتج: ${escapeHtml(job.output_file || "-")}</div>
            <div>📊 تقدم: ${p.completed_rows || 0}/${p.total_rows || 0} • فشل: ${p.failed_rows || 0}</div>
          </div>
          <div class="actions">
            <button class="btn ghost btn-pick" data-id="${job.id}">🎯 اختيار</button>
            <button class="btn ghost btn-refresh" data-id="${job.id}">🔄 تحديث</button>
            ${
              job.output_file
                ? `<button class="btn secondary btn-download" data-id="${job.id}">⬇️ تنزيل</button>`
                : ""
            }
            ${
              ["queued", "running"].includes(job.state)
                ? `<button class="btn ghost btn-cancel" data-id="${job.id}">⛔ إلغاء</button>`
                : ""
            }
          </div>
        </div>
      `;
    })
    .join("");

  els.jobsList.querySelectorAll(".btn-pick").forEach((btn) =>
    btn.addEventListener("click", async (e) => {
      const id = e.currentTarget.dataset.id;
      els.jobIdInput.value = id;
      latestJobId = id;
      await refreshSelectedJob();
    })
  );

  els.jobsList.querySelectorAll(".btn-refresh").forEach((btn) =>
    btn.addEventListener("click", async (e) => {
      const id = e.currentTarget.dataset.id;
      try {
        const job = await getJob(id);
        if (id === (els.jobIdInput.value || latestJobId)) {
          renderJobSummary(job);
        }
        setFlash(`تم تحديث ${id}`, "neutral");
        await loadJobs();
      } catch (err) {
        setFlash(`تعذر تحديث ${id}: ${err.message || err}`, "error");
      }
    })
  );

  els.jobsList.querySelectorAll(".btn-download").forEach((btn) =>
    btn.addEventListener("click", (e) => {
      const id = e.currentTarget.dataset.id;
      window.open(`/jobs/${encodeURIComponent(id)}/download`, "_blank");
    })
  );

  els.jobsList.querySelectorAll(".btn-cancel").forEach((btn) =>
    btn.addEventListener("click", async (e) => {
      const id = e.currentTarget.dataset.id;
      try {
        const response = await fetch(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "فشل الإلغاء");
        setFlash(`تم طلب إلغاء المهمة ${id}`, "ok");
        if ((els.jobIdInput.value || "").trim() === id) {
          renderJobSummary(data.job);
        }
        await loadJobs();
      } catch (err) {
        setFlash(`تعذّر إلغاء ${id}: ${err.message || err}`, "error");
      }
    })
  );
}

function downloadSelectedJob() {
  const jobId = (els.jobIdInput.value || latestJobId).trim();
  if (!jobId) {
    setFlash("أدخل رقم مهمة أولًا", "error");
    return;
  }
  window.open(`/jobs/${encodeURIComponent(jobId)}/download`, "_blank");
}

function bindLivePreview() {
  const fields = [
    "sourceMode",
    "provider",
    "modelName",
    "openrouterModelSearch",
    "openrouterModelSelect",
    "apiKey",
    "baseUrl",
    "inputColumns",
    "inputTemplate",
    "sheetName",
    "modelColumn",
    "instructionMode",
    "instructionColumn",
    "fixedInstruction",
    "systemPrompt",
    "userTemplate",
    "splitMode",
    "delimiter",
    "outputColumns",
    "outputFileName",
    "targetSheetName",
    "targetStartRow",
    "targetStartColumn",
    "writeHeaders",
    "exportColumns",
    "globalConcurrency",
    "providerConcurrency",
    "temperature",
    "retries",
    "startRow",
    "endRow",
    "skipCompleted",
    "strictParse",
    "statusColumn",
    "errorColumn",
    "rawOutputColumn",
  ];
  fields.forEach((id) => {
    const el = els[id];
    const evt = el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(evt, () => {
      if (id === "sourceMode") toggleSourceMode();
      refreshConfigPreview();
    });
  });
}

function init() {
  toggleSourceMode();
  bindLivePreview();
  refreshConfigPreview();
  loadJobs();

  els.btnRun.addEventListener("click", runJob);
  els.btnRefreshJob.addEventListener("click", refreshSelectedJob);
  els.btnPollToggle.addEventListener("click", togglePolling);
  els.btnDownloadJob.addEventListener("click", downloadSelectedJob);
  els.btnLoadJobs.addEventListener("click", loadJobs);
  els.btnLoadJobsTop.addEventListener("click", loadJobs);
  els.applyMockPreset.addEventListener("click", applyMockPreset);
  els.applyOpenRouterPreset.addEventListener("click", applyOpenRouterPreset);
  els.provider.addEventListener("change", () => {
    handleProviderChange().catch(() => {});
  });
  els.btnReloadOpenrouterModels.addEventListener("click", () => {
    loadOpenrouterModels(true).catch(() => {});
  });
  els.openrouterModelSelect.addEventListener("change", () => {
    els.modelName.value = els.openrouterModelSelect.value || els.modelName.value;
    refreshConfigPreview();
  });
  els.openrouterModelSearch.addEventListener("input", () => {
    applyOpenrouterFilter();
    refreshConfigPreview();
  });

  handleProviderChange().catch(() => {});
}

init();
