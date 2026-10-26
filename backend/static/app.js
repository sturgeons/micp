const STORAGE_KEYS = {
  schemes: "micp_schemes",
  templates: "micp_templates",
  dataset: "micp_dataset",
  report: "micp_report",
  authToken: "micp_auth_token",
  projectId: "micp_project_id",
};

const API_BASE = `${window.location.origin}/api`;

const PARAM_DEFS = [
  { key: "dryDensity", label: "砂土干密度", unit: "g/cm³", min: 1.2, max: 2.2 },
  { key: "fiberContent", label: "椰壳纤维掺量", unit: "%", min: 0, max: 1 },
  { key: "bacterialVolume", label: "菌液用量", unit: "mL", min: 10, max: 300 },
  { key: "odValue", label: "菌落 OD 值", unit: "", min: 0.2, max: 3 },
  { key: "temperature", label: "固化温度", unit: "℃", min: 20, max: 40 },
  { key: "cementationDose", label: "固化剂用量", unit: "g/L", min: 0.1, max: 3 },
  { key: "fixationVolume", label: "固定液用量", unit: "mL", min: 10, max: 300 },
  { key: "cycles", label: "固化次数", unit: "次", min: 1, max: 10 },
];

const METRIC_DEFS = [
  { key: "ucs", label: "无侧限抗压强度", unit: "kPa" },
  { key: "postDryDensity", label: "固化后干密度", unit: "g/cm³" },
  { key: "disintegrationRate", label: "浸水崩解率", unit: "%" },
  { key: "permeability", label: "渗透系数", unit: "10⁻⁶ cm/s" },
  { key: "frictionAngle", label: "内摩擦角", unit: "°" },
  { key: "cohesion", label: "黏聚力", unit: "kPa" },
  { key: "caco3", label: "碳酸钙含量", unit: "%" },
];

const demoDataset = [
  {
    sampleId: "S01",
    dryDensity: 1.56,
    fiberContent: 0.15,
    bacterialVolume: 100,
    odValue: 1.0,
    temperature: 25,
    cementationDose: 0.7,
    fixationVolume: 80,
    cycles: 3,
    ucs: 490,
    postDryDensity: 1.72,
    disintegrationRate: 20.4,
    permeability: 6.4,
    frictionAngle: 31.2,
    cohesion: 41,
    caco3: 9.8,
  },
  {
    sampleId: "S02",
    dryDensity: 1.60,
    fiberContent: 0.30,
    bacterialVolume: 120,
    odValue: 1.2,
    temperature: 30,
    cementationDose: 0.8,
    fixationVolume: 90,
    cycles: 4,
    ucs: 685,
    postDryDensity: 1.79,
    disintegrationRate: 14.1,
    permeability: 4.9,
    frictionAngle: 34.7,
    cohesion: 56,
    caco3: 13.5,
  },
  {
    sampleId: "S03",
    dryDensity: 1.63,
    fiberContent: 0.35,
    bacterialVolume: 135,
    odValue: 1.35,
    temperature: 32,
    cementationDose: 1.0,
    fixationVolume: 105,
    cycles: 5,
    ucs: 756,
    postDryDensity: 1.84,
    disintegrationRate: 11.4,
    permeability: 4.2,
    frictionAngle: 36.4,
    cohesion: 63,
    caco3: 15.1,
  },
  {
    sampleId: "S04",
    dryDensity: 1.58,
    fiberContent: 0.45,
    bacterialVolume: 140,
    odValue: 1.4,
    temperature: 35,
    cementationDose: 1.1,
    fixationVolume: 110,
    cycles: 5,
    ucs: 732,
    postDryDensity: 1.82,
    disintegrationRate: 12.6,
    permeability: 4.4,
    frictionAngle: 35.8,
    cohesion: 60,
    caco3: 14.4,
  },
  {
    sampleId: "S05",
    dryDensity: 1.67,
    fiberContent: 0.20,
    bacterialVolume: 115,
    odValue: 1.1,
    temperature: 28,
    cementationDose: 0.9,
    fixationVolume: 95,
    cycles: 4,
    ucs: 648,
    postDryDensity: 1.81,
    disintegrationRate: 15.2,
    permeability: 5.1,
    frictionAngle: 33.8,
    cohesion: 52,
    caco3: 12.7,
  },
  {
    sampleId: "S06",
    dryDensity: 1.62,
    fiberContent: 0.55,
    bacterialVolume: 150,
    odValue: 1.5,
    temperature: 31,
    cementationDose: 1.2,
    fixationVolume: 120,
    cycles: 6,
    ucs: 801,
    postDryDensity: 1.88,
    disintegrationRate: 10.3,
    permeability: 3.9,
    frictionAngle: 37.1,
    cohesion: 66,
    caco3: 16.0,
  },
];

const defaultSchemes = [
  {
    schemeName: "标准方案 A",
    dryDensity: 1.6,
    fiberContent: 0.3,
    bacterialVolume: 120,
    odValue: 1.2,
    temperature: 30,
    cementationDose: 0.8,
    fixationVolume: 90,
    cycles: 4,
  },
  {
    schemeName: "高强增强方案",
    dryDensity: 1.64,
    fiberContent: 0.48,
    bacterialVolume: 145,
    odValue: 1.45,
    temperature: 32,
    cementationDose: 1.1,
    fixationVolume: 112,
    cycles: 5,
  },
];

const state = {
  schemes: loadState(STORAGE_KEYS.schemes, defaultSchemes),
  templates: loadState(STORAGE_KEYS.templates, []),
  dataset: loadState(STORAGE_KEYS.dataset, demoDataset),
  lastPrediction: null,
  lastAnalysis: null,
  backend: {
    available: false,
    url: API_BASE,
    trainedModels: [],
    mlAvailable: false,
    mlError: "",
    trainingMetrics: {},
    comparisonRanking: [],
  },
  auth: {
    token: localStorage.getItem(STORAGE_KEYS.authToken) || "",
    user: null,
    projects: [],
    currentProjectId: localStorage.getItem(STORAGE_KEYS.projectId) || "",
  },
};

const els = {
  form: document.querySelector("#parameter-form"),
  validation: document.querySelector("#validation-message"),
  schemeTable: document.querySelector("#scheme-table"),
  templateSelect: document.querySelector("#template-select"),
  predictionScheme: document.querySelector("#prediction-scheme"),
  predictionModel: document.querySelector("#prediction-model"),
  predictionGrid: document.querySelector("#prediction-grid"),
  sensitivityList: document.querySelector("#sensitivity-list"),
  recommendation: document.querySelector("#recommendation"),
  datasetTable: document.querySelector("#dataset-table"),
  datasetMeta: document.querySelector("#dataset-meta"),
  statsSummary: document.querySelector("#stats-summary"),
  analysisDetail: document.querySelector("#analysis-detail"),
  reportPreview: document.querySelector("#report-preview"),
  chartX: document.querySelector("#chart-x"),
  chartY: document.querySelector("#chart-y"),
  chartType: document.querySelector("#chart-type"),
  chartCanvas: document.querySelector("#chart-canvas"),
  schemeCount: document.querySelector("#scheme-count"),
  datasetCount: document.querySelector("#dataset-count"),
  backendStatus: document.querySelector("#backend-status"),
  currentUser: document.querySelector("#current-user"),
  currentProject: document.querySelector("#current-project"),
  mlStatus: document.querySelector("#ml-status"),
  globalFeedback: document.querySelector("#global-feedback"),
  authUsername: document.querySelector("#auth-username"),
  authPassword: document.querySelector("#auth-password"),
  authStatus: document.querySelector("#auth-status"),
  projectName: document.querySelector("#project-name"),
  projectDescription: document.querySelector("#project-description"),
  projectSelect: document.querySelector("#project-select"),
  projectStatus: document.querySelector("#project-status"),
  trainingMetrics: document.querySelector("#training-metrics"),
  schemeRanking: document.querySelector("#scheme-ranking"),
  reportMeta: document.querySelector("#report-meta"),
};

init();

async function init() {
  bindEvents();
  await syncWithBackend();
  hydrateSelectors();
  renderAll();
}

function bindEvents() {
  els.form.addEventListener("submit", handleSchemeSave);
  document.querySelector("#save-template").addEventListener("click", saveTemplate);
  document.querySelector("#apply-template").addEventListener("click", applyTemplate);
  document.querySelector("#export-params").addEventListener("click", exportSchemes);
  document.querySelector("#batch-import").addEventListener("change", (event) => importCsv(event, "schemes"));
  document.querySelector("#dataset-import").addEventListener("change", (event) => importCsv(event, "dataset"));
  document.querySelector("#export-dataset").addEventListener("click", exportDataset);
  document.querySelector("#seed-dataset").addEventListener("click", seedDemo);
  document.querySelector("#run-prediction").addEventListener("click", runPrediction);
  document.querySelector("#compare-schemes").addEventListener("click", compareSchemes);
  document.querySelector("#run-analysis").addEventListener("click", runAnalysis);
  document.querySelector("#render-chart").addEventListener("click", renderChart);
  document.querySelector("#export-report").addEventListener("click", exportReport);
  document.querySelector("#seed-demo").addEventListener("click", seedDemo);
  document.querySelector("#train-models").addEventListener("click", trainModels);
  document.querySelector("#register-user").addEventListener("click", registerUser);
  document.querySelector("#login-user").addEventListener("click", loginUser);
  document.querySelector("#logout-user").addEventListener("click", logoutUser);
  document.querySelector("#create-project").addEventListener("click", createProject);
  document.querySelector("#refresh-projects").addEventListener("click", loadProjects);
  els.projectSelect.addEventListener("change", switchProject);
}

async function handleSchemeSave(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const scheme = Object.fromEntries(formData.entries());
  PARAM_DEFS.forEach((param) => {
    scheme[param.key] = Number(scheme[param.key]);
  });

  const error = validateScheme(scheme);
  if (error) {
    els.validation.textContent = error;
    setFeedback(error, "error");
    return;
  }

  const index = state.schemes.findIndex((item) => item.schemeName === scheme.schemeName);
  if (index >= 0) {
    state.schemes[index] = scheme;
  } else {
    state.schemes.unshift(scheme);
  }

  try {
    if (state.backend.available) {
      await api("/schemes", {
        method: "POST",
        body: JSON.stringify({ schemes: [scheme] }),
      });
    }

    persist(STORAGE_KEYS.schemes, state.schemes);
    els.validation.textContent = `方案「${scheme.schemeName}」已保存。`;
    setFeedback(`方案「${scheme.schemeName}」已同步到当前工作区。`, "success");
    hydrateSelectors();
    renderAll();
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

function saveTemplate() {
  const formData = new FormData(els.form);
  const scheme = Object.fromEntries(formData.entries());
  PARAM_DEFS.forEach((param) => {
    scheme[param.key] = Number(scheme[param.key]);
  });
  const error = validateScheme(scheme);
  if (error) {
    els.validation.textContent = error;
    setFeedback(error, "error");
    return;
  }

  const template = { ...scheme, templateName: `${scheme.schemeName}-模板` };
  state.templates = [template, ...state.templates.filter((item) => item.templateName !== template.templateName)];
  persist(STORAGE_KEYS.templates, state.templates);
  hydrateSelectors();
  els.validation.textContent = `模板「${template.templateName}」已保存。`;
  setFeedback(`模板「${template.templateName}」已保存，可在不同项目间复用。`, "success");
}

function applyTemplate() {
  const template = state.templates.find((item) => item.templateName === els.templateSelect.value);
  if (!template) {
    els.validation.textContent = "请先选择模板。";
    setFeedback("请先选择一个模板再回填参数。", "error");
    return;
  }

  Object.entries(template).forEach(([key, value]) => {
    if (key === "templateName") return;
    const field = els.form.elements.namedItem(key);
    if (field) {
      field.value = value;
    }
  });
  els.validation.textContent = `模板「${template.templateName}」已应用。`;
  setFeedback(`模板「${template.templateName}」已回填到参数表单。`, "success");
}

function validateScheme(scheme) {
  if (!scheme.schemeName?.trim()) return "方案名称不能为空。";
  for (const param of PARAM_DEFS) {
    const value = Number(scheme[param.key]);
    if (!Number.isFinite(value)) return `${param.label} 必须为数值。`;
    if (value < param.min || value > param.max) {
      return `${param.label} 超出建议范围 ${param.min}~${param.max}${param.unit}。`;
    }
  }
  return "";
}

function importCsv(event, type) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const rows = parseCsv(String(reader.result || ""));
      if (!rows.length) {
        setFeedback("CSV 内容为空或缺少表头。", "error");
        return;
      }

      const normalized = rows.map((row, index) => normalizeRow(row, type, index));
      if (type === "schemes") {
        state.schemes = [...normalized, ...state.schemes];
        if (state.backend.available) {
          await api("/schemes", {
            method: "POST",
            body: JSON.stringify({ schemes: normalized }),
          });
        }
        persist(STORAGE_KEYS.schemes, state.schemes);
        els.validation.textContent = `已导入 ${normalized.length} 组参数方案。`;
        setFeedback(`已批量导入 ${normalized.length} 组参数方案。`, "success");
      } else {
        state.dataset = normalized;
        if (state.backend.available) {
          await api("/dataset", {
            method: "POST",
            body: JSON.stringify({ rows: normalized }),
          });
        }
        persist(STORAGE_KEYS.dataset, state.dataset);
        els.datasetMeta.textContent = `已导入 ${normalized.length} 条历史样本，可用于校准模型与统计分析。`;
        setFeedback(`已导入 ${normalized.length} 条历史样本。`, "success");
      }

      hydrateSelectors();
      renderAll();
    } catch (error) {
      setFeedback(safeText(error), "error");
    } finally {
      event.target.value = "";
    }
  };
  reader.readAsText(file, "utf-8");
}

function normalizeRow(row, type, index) {
  const normalized = {};
  Object.entries(row).forEach(([key, value]) => {
    const trimmedKey = key.trim();
    const rawValue = String(value).trim();
    normalized[trimmedKey] = rawValue === "" ? "" : Number.isFinite(Number(rawValue)) ? Number(rawValue) : rawValue;
  });

  if (type === "schemes") {
    normalized.schemeName = normalized.schemeName || `批量方案-${index + 1}`;
  } else {
    normalized.sampleId = normalized.sampleId || `D${String(index + 1).padStart(2, "0")}`;
  }
  return normalized;
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    return headers.reduce((acc, header, index) => {
      acc[header] = values[index] ?? "";
      return acc;
    }, {});
  });
}

function splitCsvLine(line) {
  const result = [];
  let current = "";
  let quoted = false;

  for (const char of line) {
    if (char === '"') {
      quoted = !quoted;
      continue;
    }
    if (char === "," && !quoted) {
      result.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  result.push(current);
  return result.map((item) => item.trim());
}

async function runPrediction() {
  try {
    const scheme = state.schemes.find((item) => item.schemeName === els.predictionScheme.value) || state.schemes[0];
    if (!scheme) {
      setFeedback("当前没有可用于预测的方案。", "error");
      return;
    }

    const model = els.predictionModel.value;
    let prediction = predictMetrics(scheme, model, state.dataset);
    if (state.backend.available) {
      const remote = await api("/predict", {
        method: "POST",
        body: JSON.stringify({ scheme, model }),
      });
      if (remote?.metrics) {
        prediction = remote;
      }
    }
    state.lastPrediction = {
      schemeName: scheme.schemeName,
      model,
      metrics: prediction.metrics,
      sensitivity: prediction.sensitivity,
    };

    renderPrediction();
    renderReportPreview();
    setFeedback(`已完成方案「${scheme.schemeName}」的 ${model.toUpperCase()} 预测。`, "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

async function compareSchemes() {
  if (!state.schemes.length) {
    setFeedback("请先录入或导入方案后再进行综合排序。", "error");
    return;
  }
  try {
    let ranking = [];
    if (state.backend.available && state.backend.mlAvailable) {
      const remoteResults = await Promise.all(
        state.schemes.map(async (scheme) => {
          const prediction = await api("/predict", {
            method: "POST",
            body: JSON.stringify({ scheme, model: "ensemble" }),
          });
          return buildRankingEntry(scheme, prediction.metrics);
        })
      );
      ranking = remoteResults.sort((a, b) => b.score - a.score);
    } else {
      ranking = state.schemes
        .map((scheme) => buildRankingEntry(scheme, predictMetrics(scheme, "ensemble", state.dataset).metrics))
        .sort((a, b) => b.score - a.score);
    }

    state.backend.comparisonRanking = ranking.slice(0, 5);
    const best = ranking[0];
    els.recommendation.innerHTML = `
      <h4>最优固化方案推荐</h4>
      <p><strong>${best.scheme.schemeName}</strong> 综合得分最高，预测 UCS 为 ${formatNumber(best.metrics.ucs)} kPa，浸水崩解率 ${formatNumber(best.metrics.disintegrationRate)}%，适合作为当前优先试验组合。</p>
    `;
    renderSchemeRanking();
    renderReportPreview();
    setFeedback("已完成多方案综合排序，并更新推荐结果。", "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

function predictMetrics(scheme, model, dataset) {
  const stats = calibrationStats(dataset);
  const inputs = PARAM_DEFS.reduce((acc, item) => {
    acc[item.key] = Number(scheme[item.key]);
    return acc;
  }, {});

  const normalized = {
    density: scale(inputs.dryDensity, 1.2, 2.2),
    fiber: scale(inputs.fiberContent, 0, 1),
    bacteria: scale(inputs.bacterialVolume, 10, 300),
    od: scale(inputs.odValue, 0.2, 3),
    temp: scale(inputs.temperature, 20, 40),
    dose: scale(inputs.cementationDose, 0.1, 3),
    fix: scale(inputs.fixationVolume, 10, 300),
    cycles: scale(inputs.cycles, 1, 10),
  };

  const boost = model === "bp" ? 1.03 : 1;
  const fiberPeak = Math.max(0, 1 - Math.abs(inputs.fiberContent - 0.42) / 0.42);

  const metrics = {
    ucs: clamp(
      (380 + normalized.density * 90 + normalized.bacteria * 120 + normalized.od * 80 + normalized.dose * 120 + normalized.cycles * 145 + fiberPeak * 95 - normalized.temp * 30 + stats.ucs.mean * 0.18) * boost,
      250,
      1200
    ),
    postDryDensity: clamp(1.55 + normalized.density * 0.18 + normalized.cycles * 0.06 + normalized.dose * 0.07 + stats.postDryDensity.mean * 0.08, 1.55, 2.15),
    disintegrationRate: clamp(28 - normalized.dose * 8 - normalized.cycles * 7 - fiberPeak * 6 - normalized.od * 3 + normalized.temp * 4 - stats.caco3.mean * 0.1, 3, 35),
    permeability: clamp(7.8 - normalized.dose * 1.5 - normalized.cycles * 1.2 - normalized.fix * 0.6 - fiberPeak * 0.9, 1.8, 9.5),
    frictionAngle: clamp(28 + normalized.density * 3 + normalized.dose * 2.8 + normalized.cycles * 4.8 + fiberPeak * 2.5, 24, 45),
    cohesion: clamp(24 + normalized.dose * 18 + normalized.cycles * 15 + normalized.bacteria * 10 + fiberPeak * 8, 15, 120),
    caco3: clamp(6 + normalized.bacteria * 4 + normalized.od * 5 + normalized.dose * 4.5 + normalized.cycles * 4.5 + normalized.fix * 2.2, 3, 28),
  };

  metrics.postDryDensity = clamp(1.55 + normalized.density * 0.14 + normalized.dose * 0.06 + normalized.cycles * 0.08 + metrics.caco3 * 0.004, 1.55, 2.2);

  const weights = {
    dryDensity: 0.11,
    fiberContent: 0.18,
    bacterialVolume: 0.12,
    odValue: 0.11,
    temperature: 0.08,
    cementationDose: 0.16,
    fixationVolume: 0.09,
    cycles: 0.15,
  };

  const sensitivity = Object.entries(weights)
    .map(([key, weight]) => {
      const param = PARAM_DEFS.find((item) => item.key === key);
      const dynamic = Math.abs((inputs[key] - param.min) / (param.max - param.min) - 0.5);
      return {
        key,
        label: param.label,
        score: weight + dynamic * 0.08 + (key === "fiberContent" ? fiberPeak * 0.06 : 0),
      };
    })
    .sort((a, b) => b.score - a.score);

  return { metrics, sensitivity };
}

async function runAnalysis() {
  if (!state.dataset.length) {
    setFeedback("请先导入历史样本数据。", "error");
    return;
  }
  try {
    state.lastAnalysis = null;
    if (state.backend.available) {
      const remote = await api("/analyze", { method: "POST" });
      if (remote) {
        state.lastAnalysis = remote;
      }
    }

    if (!state.lastAnalysis) {
      const cleanDataset = detectOutliers(state.dataset);
      const removed = state.dataset.length - cleanDataset.length;
      const metricStats = METRIC_DEFS.map((metric) => {
        const values = cleanDataset.map((item) => Number(item[metric.key])).filter(Number.isFinite);
        return {
          key: metric.key,
          label: metric.label,
          mean: mean(values),
          std: std(values),
          cv: coefficientOfVariation(values),
        };
      });

      const groups = groupBy(cleanDataset, "fiberContent");
      const anovaValues = Object.values(groups)
        .map((items) => items.map((item) => Number(item.ucs)).filter(Number.isFinite))
        .filter((items) => items.length > 0);
      const anova = oneWayAnova(anovaValues);
      state.lastAnalysis = { metricStats, removed, anova, sampleSize: cleanDataset.length };
    }
    renderAnalysis();
    renderReportPreview();
    setFeedback("统计分析已完成，描述统计与 ANOVA 已更新。", "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

function detectOutliers(dataset) {
  const ucsValues = dataset.map((item) => Number(item.ucs)).filter(Number.isFinite).sort((a, b) => a - b);
  if (ucsValues.length < 4) return [...dataset];
  const q1 = quantile(ucsValues, 0.25);
  const q3 = quantile(ucsValues, 0.75);
  const iqr = q3 - q1;
  const lower = q1 - 1.5 * iqr;
  const upper = q3 + 1.5 * iqr;
  return dataset.filter((item) => item.ucs >= lower && item.ucs <= upper);
}

function renderAll() {
  renderSchemes();
  renderDataset();
  renderPrediction();
  renderTrainingMetrics();
  renderSchemeRanking();
  renderAnalysis();
  renderReportPreview();
  renderChart();
  updateMetrics();
  renderStatusStrip();
}

function renderSchemes() {
  els.schemeTable.innerHTML = state.schemes
    .slice(0, 12)
    .map(
      (scheme) => `
      <tr>
        <td>${scheme.schemeName}</td>
        <td>${formatNumber(scheme.fiberContent)}</td>
        <td>${formatNumber(scheme.temperature)}</td>
        <td>${formatNumber(scheme.cycles)}</td>
      </tr>
    `
    )
    .join("");
}

function renderDataset() {
  els.datasetTable.innerHTML = state.dataset
    .slice(0, 12)
    .map(
      (row) => `
      <tr>
        <td>${row.sampleId || "-"}</td>
        <td>${formatNumber(row.ucs)}</td>
        <td>${formatNumber(row.postDryDensity)}</td>
        <td>${formatNumber(row.caco3)}</td>
      </tr>
    `
    )
    .join("");
  els.datasetMeta.textContent ||= `当前已加载 ${state.dataset.length} 条历史样本。`;
}

function renderPrediction() {
  if (!state.schemes.length) {
    els.predictionGrid.innerHTML = "<p class=\"message\">请先录入方案后再执行预测。</p>";
    els.sensitivityList.innerHTML = "";
    return;
  }
  if (!state.lastPrediction) {
    const initial = predictMetrics(state.schemes[0], "ensemble", state.dataset);
    state.lastPrediction = {
      schemeName: state.schemes[0]?.schemeName || "标准方案",
      model: "ensemble",
      metrics: initial.metrics,
      sensitivity: initial.sensitivity,
    };
  }

  els.predictionGrid.innerHTML = METRIC_DEFS.map((metric) => {
    const value = state.lastPrediction.metrics[metric.key];
    return `
      <div class="result-item">
        <span>${metric.label}</span>
        <strong>${formatNumber(value)} ${metric.unit}</strong>
      </div>
    `;
  }).join("");

  els.sensitivityList.innerHTML = state.lastPrediction.sensitivity
    .slice(0, 6)
    .map((item) => `<li>${item.label} 影响权重 ${formatNumber(item.score * 100, 1)}%</li>`)
    .join("");
}

function renderTrainingMetrics() {
  const metrics = state.backend.trainingMetrics || {};
  const rows = Object.entries(metrics);
  if (!rows.length) {
    els.trainingMetrics.innerHTML = `
      <div class="stats-item">
        <span>训练概况</span>
        <strong>${state.backend.trainedModels.length ? "模型已就绪" : "待训练"}</strong>
        <span>${state.backend.trainedModels.length ? state.backend.trainedModels.join("、") : "点击上方按钮训练模型"}</span>
      </div>
    `;
    return;
  }

  els.trainingMetrics.innerHTML = rows
    .map(([modelName, detail]) => {
      const score = firstFinite(detail?.r2, detail?.score, detail?.mean_r2);
      const loss = firstFinite(detail?.rmse, detail?.mse, detail?.mae);
      return `
        <div class="stats-item">
          <span>${modelName.toUpperCase()} 训练表现</span>
          <strong>${score !== null ? formatNumber(score, 3) : "已完成"}</strong>
          <span>${loss !== null ? `误差 ${formatNumber(loss, 3)}` : "指标已记录到后端模型仓库"}</span>
        </div>
      `;
    })
    .join("");
}

function renderSchemeRanking() {
  const ranking = state.backend.comparisonRanking || [];
  if (!ranking.length) {
    els.schemeRanking.innerHTML = "<p class=\"message\">点击“筛选最优方案”后，这里会显示综合排序结果。</p>";
    return;
  }

  els.schemeRanking.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>排名</th>
          <th>方案</th>
          <th>综合分</th>
          <th>UCS</th>
          <th>崩解率</th>
        </tr>
      </thead>
      <tbody>
        ${ranking
          .map(
            (item, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${item.scheme.schemeName}</td>
                <td>${formatNumber(item.score)}</td>
                <td>${formatNumber(item.metrics.ucs)}</td>
                <td>${formatNumber(item.metrics.disintegrationRate)}%</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderAnalysis() {
  if (!state.lastAnalysis) {
    els.statsSummary.innerHTML = "";
    els.analysisDetail.innerHTML = "导入数据后点击“执行统计分析”，可自动完成描述统计、异常值检测与 ANOVA。";
    return;
  }

  els.statsSummary.innerHTML = state.lastAnalysis.metricStats
    .slice(0, 4)
    .map(
      (item) => `
      <div class="stats-item">
        <span>${item.label}</span>
        <strong>${formatNumber(item.mean)}</strong>
        <span>Std ${formatNumber(item.std)} / CV ${formatNumber(item.cv * 100)}%</span>
      </div>
    `
    )
    .join("");

  els.analysisDetail.innerHTML = `
    <p>有效样本数 ${state.lastAnalysis.sampleSize}，剔除异常值 ${state.lastAnalysis.removed} 条。</p>
    <p>纤维掺量对 UCS 的单因素方差分析结果：F = ${formatNumber(state.lastAnalysis.anova.fValue)}，组间显著性指标 = ${formatNumber(state.lastAnalysis.anova.effect, 3)}。</p>
    <p>结论建议：在当前样本下，纤维掺量与固化剂用量是影响强度提升的主要因素，可优先围绕 0.30%~0.55% 纤维区间做细化试验。</p>
  `;
}

function renderReportPreview() {
  const scheme = state.schemes.find((item) => item.schemeName === (state.lastPrediction?.schemeName || state.schemes[0]?.schemeName)) || state.schemes[0];
  const prediction = state.lastPrediction;
  const analysis = state.lastAnalysis;
  const metricsHtml = prediction
    ? `<ul>${METRIC_DEFS.map((metric) => `<li>${metric.label}：${formatNumber(prediction.metrics[metric.key])} ${metric.unit}</li>`).join("")}</ul>`
    : "<p>暂无预测结果。</p>";
  const sensitivityHtml = prediction
    ? `<ol>${prediction.sensitivity.slice(0, 5).map((item) => `<li>${item.label}（${formatNumber(item.score * 100, 1)}%）</li>`).join("")}</ol>`
    : "";
  const topRanking = state.backend.comparisonRanking[0];
  els.reportMeta.textContent = `报告上下文：${state.auth.user?.username || "离线用户"} / ${
    currentProjectName() || "默认项目"
  } / ${prediction?.model?.toUpperCase() || "未预测"} / ${new Date().toLocaleString("zh-CN")}`;

  els.reportPreview.innerHTML = `
    <h3>1. 参数配置</h3>
    <p>${scheme ? PARAM_DEFS.map((param) => `${param.label} ${scheme[param.key]}${param.unit}`).join("；") : "暂无方案数据。"}。</p>
    <h3>2. 性能预测结果</h3>
    ${metricsHtml}
    <h4>影响因素排序</h4>
    ${sensitivityHtml}
    <h3>3. 数据处理与统计分析</h3>
    <p>${
      analysis
        ? `样本数 ${analysis.sampleSize}，异常值剔除 ${analysis.removed} 条，UCS 方差分析 F 值 ${formatNumber(analysis.anova.fValue)}。`
        : "尚未执行统计分析。"
    }</p>
    <h3>4. 结论建议</h3>
    <p>推荐以纤维掺量、固化剂用量与固化次数为核心调参方向，优先验证高强增强组合与标准方案之间的性能差异，并同步记录碳酸钙含量与渗透系数变化。</p>
    <p>${topRanking ? `综合排序当前领先方案为 ${topRanking.scheme.schemeName}，综合得分 ${formatNumber(topRanking.score)}。` : "尚未执行多方案综合排序。"}</p>
  `;
}

function renderChart() {
  const ctx = els.chartCanvas.getContext("2d");
  const width = els.chartCanvas.width;
  const height = els.chartCanvas.height;
  ctx.clearRect(0, 0, width, height);

  const chartType = els.chartType.value || "line";
  const xKey = els.chartX.value || "fiberContent";
  const yKey = els.chartY.value || "ucs";
  const data = state.dataset.filter((item) => Number.isFinite(Number(item[xKey])) && Number.isFinite(Number(item[yKey])));

  drawBackground(ctx, width, height);
  if (!data.length) {
    ctx.fillStyle = "#5c695f";
    ctx.font = "20px Manrope";
    ctx.fillText("请先导入历史数据或载入示例数据", 180, 210);
    return;
  }

  switch (chartType) {
    case "bar":
      drawBarChart(ctx, width, height, data, xKey, yKey);
      break;
    case "box":
      drawBoxPlot(ctx, width, height, data, xKey, yKey);
      break;
    case "heatmap":
      drawHeatmap(ctx, width, height, data);
      break;
    default:
      drawLineChart(ctx, width, height, data, xKey, yKey);
      break;
  }
}

function drawBackground(ctx, width, height) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "rgba(15,106,82,0.08)");
  gradient.addColorStop(1, "rgba(176,100,44,0.07)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(31,47,41,0.1)";
  for (let i = 40; i < width; i += 60) {
    ctx.beginPath();
    ctx.moveTo(i, 30);
    ctx.lineTo(i, height - 40);
    ctx.stroke();
  }
  for (let i = 30; i < height; i += 60) {
    ctx.beginPath();
    ctx.moveTo(40, i);
    ctx.lineTo(width - 40, i);
    ctx.stroke();
  }
}

function drawAxes(ctx, width, height, xLabel, yLabel) {
  ctx.strokeStyle = "#1f2f29";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(60, height - 50);
  ctx.lineTo(width - 30, height - 50);
  ctx.moveTo(60, height - 50);
  ctx.lineTo(60, 40);
  ctx.stroke();
  ctx.fillStyle = "#1f2f29";
  ctx.font = "16px Manrope";
  ctx.fillText(xLabel, width / 2 - 40, height - 15);
  ctx.save();
  ctx.translate(20, height / 2 + 30);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();
}

function drawLineChart(ctx, width, height, data, xKey, yKey) {
  const sorted = [...data].sort((a, b) => a[xKey] - b[xKey]);
  const xValues = sorted.map((item) => item[xKey]);
  const yValues = sorted.map((item) => item[yKey]);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  drawAxes(ctx, width, height, labelOf(xKey), labelOf(yKey));
  ctx.strokeStyle = "#0f6a52";
  ctx.lineWidth = 3;
  ctx.beginPath();
  sorted.forEach((item, index) => {
    const x = map(item[xKey], xMin, xMax, 80, width - 60);
    const y = map(item[yKey], yMin, yMax, height - 80, 70);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  sorted.forEach((item) => {
    const x = map(item[xKey], xMin, xMax, 80, width - 60);
    const y = map(item[yKey], yMin, yMax, height - 80, 70);
    ctx.fillStyle = "#b0642c";
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawBarChart(ctx, width, height, data, xKey, yKey) {
  const grouped = Object.entries(groupBy(data, xKey)).slice(0, 7);
  const values = grouped.map(([, items]) => mean(items.map((item) => item[yKey])));
  const maxValue = Math.max(...values);
  drawAxes(ctx, width, height, labelOf(xKey), `${labelOf(yKey)} 均值`);
  const barWidth = (width - 140) / grouped.length;
  grouped.forEach(([group, items], index) => {
    const value = mean(items.map((item) => item[yKey]));
    const x = 80 + index * barWidth + 10;
    const y = map(value, 0, maxValue, height - 50, 80);
    const gradient = ctx.createLinearGradient(0, y, 0, height - 50);
    gradient.addColorStop(0, "#0f6a52");
    gradient.addColorStop(1, "#94c7af");
    ctx.fillStyle = gradient;
    ctx.fillRect(x, y, barWidth - 18, height - 50 - y);
    ctx.fillStyle = "#1f2f29";
    ctx.font = "12px Manrope";
    ctx.fillText(group, x, height - 30);
    ctx.fillText(formatNumber(value), x, y - 8);
  });
}

function drawBoxPlot(ctx, width, height, data, xKey, yKey) {
  const grouped = Object.entries(groupBy(data, xKey)).slice(0, 6);
  drawAxes(ctx, width, height, labelOf(xKey), labelOf(yKey));
  const spacing = (width - 140) / grouped.length;

  grouped.forEach(([group, items], index) => {
    const values = items.map((item) => item[yKey]).sort((a, b) => a - b);
    const q1 = quantile(values, 0.25);
    const median = quantile(values, 0.5);
    const q3 = quantile(values, 0.75);
    const min = values[0];
    const max = values[values.length - 1];
    const x = 90 + index * spacing;
    const yMin = Math.min(...data.map((item) => item[yKey]));
    const yMax = Math.max(...data.map((item) => item[yKey]));

    const boxTop = map(q3, yMin, yMax, height - 80, 70);
    const boxBottom = map(q1, yMin, yMax, height - 80, 70);
    const medianY = map(median, yMin, yMax, height - 80, 70);
    const minY = map(min, yMin, yMax, height - 80, 70);
    const maxY = map(max, yMin, yMax, height - 80, 70);

    ctx.strokeStyle = "#0f6a52";
    ctx.fillStyle = "rgba(15,106,82,0.18)";
    ctx.fillRect(x, boxTop, 40, boxBottom - boxTop);
    ctx.strokeRect(x, boxTop, 40, boxBottom - boxTop);
    ctx.beginPath();
    ctx.moveTo(x + 20, maxY);
    ctx.lineTo(x + 20, boxTop);
    ctx.moveTo(x + 20, boxBottom);
    ctx.lineTo(x + 20, minY);
    ctx.moveTo(x, medianY);
    ctx.lineTo(x + 40, medianY);
    ctx.stroke();
    ctx.fillStyle = "#1f2f29";
    ctx.fillText(group, x - 4, height - 30);
  });
}

function drawHeatmap(ctx, width, height, data) {
  const xParams = ["fiberContent", "temperature", "cycles", "cementationDose"];
  const yMetrics = ["ucs", "caco3", "cohesion", "permeability"];
  const cellW = 130;
  const cellH = 70;
  ctx.font = "14px Manrope";

  xParams.forEach((param, col) => {
    ctx.fillStyle = "#1f2f29";
    ctx.fillText(labelOf(param), 95 + col * cellW, 70);
  });
  yMetrics.forEach((metric, row) => {
    ctx.fillText(labelOf(metric), 20, 120 + row * cellH);
  });

  xParams.forEach((param, col) => {
    yMetrics.forEach((metric, row) => {
      const corr = correlation(
        data.map((item) => Number(item[param])),
        data.map((item) => Number(item[metric]))
      );
      const alpha = Math.min(Math.abs(corr), 1);
      ctx.fillStyle = corr >= 0 ? `rgba(15,106,82,${0.12 + alpha * 0.7})` : `rgba(176,100,44,${0.12 + alpha * 0.7})`;
      ctx.fillRect(100 + col * cellW, 90 + row * cellH, 105, 48);
      ctx.fillStyle = "#fff";
      ctx.fillText(formatNumber(corr, 2), 135 + col * cellW, 120 + row * cellH);
    });
  });
}

function exportSchemes() {
  const headers = ["schemeName", ...PARAM_DEFS.map((item) => item.key)];
  const rows = state.schemes.map((item) => headers.map((header) => item[header]));
  downloadCsv("micp-params.csv", headers, rows);
  setFeedback(`已导出 ${rows.length} 组参数方案。`, "success");
}

function exportDataset() {
  const headers = ["sampleId", ...PARAM_DEFS.map((item) => item.key), ...METRIC_DEFS.map((item) => item.key)];
  const rows = state.dataset.map((item) => headers.map((header) => item[header] ?? ""));
  downloadCsv("micp-dataset.csv", headers, rows);
  setFeedback(`已导出 ${rows.length} 条历史样本。`, "success");
}

async function exportReport() {
  try {
    renderReportPreview();
    let reportHtml = `
      <html lang="zh-CN">
        <head>
          <meta charset="UTF-8" />
          <title>MICP 分析报告</title>
          <style>
            body { font-family: 'Songti SC', serif; padding: 40px; color: #1f2f29; line-height: 1.8; }
            h1, h2, h3, h4 { color: #0f6a52; }
            ul, ol { padding-left: 22px; }
          </style>
        </head>
        <body>${els.reportPreview.innerHTML}</body>
      </html>
    `;
    if (state.backend.available) {
      const remote = await api("/report", {
        method: "POST",
        body: JSON.stringify({
          prediction: state.lastPrediction,
          analysis: state.lastAnalysis,
        }),
      });
      if (remote?.html) {
        reportHtml = remote.html;
      }
    }
    const blob = new Blob([reportHtml], { type: "application/msword" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "micp-analysis-report.doc";
    link.click();
    URL.revokeObjectURL(url);

    const reportWindow = window.open("", "_blank");
    reportWindow.document.write(reportHtml);
    reportWindow.document.close();
    reportWindow.focus();
    setTimeout(() => reportWindow.print(), 300);
    setFeedback("分析报告已生成并打开打印预览。", "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

async function seedDemo() {
  try {
    state.dataset = demoDataset;
    state.schemes = defaultSchemes;
    state.lastAnalysis = null;
    state.backend.comparisonRanking = [];
    persist(STORAGE_KEYS.dataset, state.dataset);
    persist(STORAGE_KEYS.schemes, state.schemes);
    if (state.backend.available) {
      await api("/seed", { method: "POST" });
      await syncWithBackend();
    }
    els.datasetMeta.textContent = `已载入 ${state.dataset.length} 条示例样本。`;
    hydrateSelectors();
    await runPrediction();
    await runAnalysis();
    renderAll();
    setFeedback("示例样本与默认方案已恢复。", "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

async function trainModels() {
  if (!state.backend.available) {
    els.backendStatus.textContent = "当前运行在纯前端模式，启动后端后可训练并持久化模型。";
    setFeedback("当前是离线模式，无法调用 Flask 模型训练接口。", "error");
    return;
  }
  try {
    els.backendStatus.textContent = "正在训练集成模型与 BP 风格模型...";
    const result = await api("/train", { method: "POST" });
    state.backend.trainedModels = result?.trainedModels || [];
    state.backend.trainingMetrics = result?.metrics || {};
    els.backendStatus.textContent = `模型训练完成：${state.backend.trainedModels.join("、")}。`;
    renderTrainingMetrics();
    setFeedback(`模型训练完成：${state.backend.trainedModels.join("、")}。`, "success");
    await runPrediction();
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

async function registerUser() {
  if (!state.backend.available) {
    els.authStatus.textContent = "请先启动 Flask 后端，再使用账户体系。";
    setFeedback("Flask 服务未连接，暂时无法注册账户。", "error");
    return;
  }
  const username = els.authUsername.value.trim();
  const password = els.authPassword.value.trim();
  if (!username || !password) {
    els.authStatus.textContent = "请输入用户名和密码。";
    setFeedback("注册前请输入用户名和密码。", "error");
    return;
  }
  try {
    const result = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      omitAuth: true,
      omitProject: true,
    });
    els.authStatus.textContent = `用户 ${result.user.username} 注册成功，请继续登录。`;
    setFeedback(`用户 ${result.user.username} 注册成功。`, "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

async function loginUser() {
  if (!state.backend.available) {
    els.authStatus.textContent = "请先启动 Flask 后端，再使用账户体系。";
    setFeedback("Flask 服务未连接，暂时无法登录。", "error");
    return;
  }
  const username = els.authUsername.value.trim();
  const password = els.authPassword.value.trim();
  if (!username || !password) {
    els.authStatus.textContent = "请输入用户名和密码。";
    setFeedback("登录前请输入用户名和密码。", "error");
    return;
  }
  try {
    const result = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      omitAuth: true,
      omitProject: true,
    });
    state.auth.token = result.token;
    state.auth.user = result.user;
    localStorage.setItem(STORAGE_KEYS.authToken, result.token);
    els.authStatus.textContent = `已登录：${result.user.username}`;
    await loadProjects();
    await syncWithBackend();
    setFeedback(`欢迎回来，${result.user.username}。`, "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

function logoutUser() {
  state.auth.token = "";
  state.auth.user = null;
  state.auth.projects = [];
  state.auth.currentProjectId = "";
  localStorage.removeItem(STORAGE_KEYS.authToken);
  localStorage.removeItem(STORAGE_KEYS.projectId);
  els.authStatus.textContent = "已退出登录，当前可继续使用默认项目。";
  renderProjectOptions();
  renderStatusStrip();
  setFeedback("已退出登录，系统切换为默认项目上下文。", "success");
}

async function createProject() {
  if (!state.backend.available || !state.auth.token) {
    els.projectStatus.textContent = "请先登录，再创建项目。";
    setFeedback("请先登录后再创建项目。", "error");
    return;
  }
  const name = els.projectName.value.trim();
  const description = els.projectDescription.value.trim();
  if (!name) {
    els.projectStatus.textContent = "请输入项目名称。";
    setFeedback("请输入项目名称。", "error");
    return;
  }
  try {
    const result = await api("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
      omitProject: true,
    });
    els.projectStatus.textContent = `项目「${result.project.name}」已创建。`;
    await loadProjects(result.project.id);
    renderStatusStrip();
    setFeedback(`项目「${result.project.name}」已创建并设为当前项目。`, "success");
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

async function loadProjects(selectedId = "") {
  if (!state.backend.available || !state.auth.token) {
    renderProjectOptions();
    return;
  }
  try {
    const result = await api("/projects", { omitProject: true });
    state.auth.projects = result.projects || [];
    if (selectedId) {
      state.auth.currentProjectId = String(selectedId);
    } else if (!state.auth.currentProjectId && state.auth.projects.length) {
      state.auth.currentProjectId = String(state.auth.projects[0].id);
    } else if (!state.auth.projects.some((item) => String(item.id) === String(state.auth.currentProjectId))) {
      state.auth.currentProjectId = state.auth.projects[0] ? String(state.auth.projects[0].id) : "";
    }
    localStorage.setItem(STORAGE_KEYS.projectId, state.auth.currentProjectId || "");
    renderProjectOptions();
  } catch (error) {
    setFeedback(safeText(error), "error");
  }
}

function switchProject() {
  state.auth.currentProjectId = els.projectSelect.value;
  localStorage.setItem(STORAGE_KEYS.projectId, state.auth.currentProjectId || "");
  els.projectStatus.textContent = state.auth.currentProjectId
    ? `已切换到项目 ID ${state.auth.currentProjectId}。`
    : "当前使用默认项目。";
  renderStatusStrip();
  setFeedback(
    state.auth.currentProjectId ? `已切换到项目「${currentProjectName()}」。` : "当前使用默认项目。",
    "success"
  );
  syncWithBackend();
}

function renderProjectOptions() {
  const options = state.auth.projects.length
    ? state.auth.projects.map((item) => `<option value="${item.id}">${item.name}</option>`).join("")
    : `<option value="">默认项目</option>`;
  els.projectSelect.innerHTML = options;
  if (state.auth.currentProjectId) {
    els.projectSelect.value = state.auth.currentProjectId;
  }
  els.authStatus.textContent ||= state.auth.user ? `已登录：${state.auth.user.username}` : "未登录，当前可使用默认项目。";
  renderStatusStrip();
}

function hydrateSelectors() {
  const currentScheme = els.predictionScheme.value;
  const currentX = els.chartX.value;
  const currentY = els.chartY.value;

  els.templateSelect.innerHTML = `<option value="">选择模板后回填</option>${state.templates
    .map((item) => `<option value="${item.templateName}">${item.templateName}</option>`)
    .join("")}`;

  els.predictionScheme.innerHTML = state.schemes
    .map((item) => `<option value="${item.schemeName}">${item.schemeName}</option>`)
    .join("");
  els.predictionScheme.value = state.schemes.some((item) => item.schemeName === currentScheme)
    ? currentScheme
    : state.schemes[0]?.schemeName || "";

  const paramOptions = PARAM_DEFS.map((item) => `<option value="${item.key}">${item.label}</option>`).join("");
  const metricOptions = METRIC_DEFS.map((item) => `<option value="${item.key}">${item.label}</option>`).join("");
  els.chartX.innerHTML = paramOptions;
  els.chartY.innerHTML = metricOptions;
  els.chartX.value = PARAM_DEFS.some((item) => item.key === currentX) ? currentX : "fiberContent";
  els.chartY.value = METRIC_DEFS.some((item) => item.key === currentY) ? currentY : "ucs";
}

function updateMetrics() {
  els.schemeCount.textContent = state.schemes.length;
  els.datasetCount.textContent = state.dataset.length;
}

function calibrationStats(dataset) {
  const source = dataset.length ? dataset : demoDataset;
  const stats = {};
  METRIC_DEFS.forEach((metric) => {
    const values = source.map((item) => Number(item[metric.key])).filter(Number.isFinite);
    stats[metric.key] = {
      mean: mean(values),
      std: std(values),
    };
  });
  stats.cycleSmoothing = { mean: 0.02 };
  return stats;
}

function mean(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function std(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  const variance = values.reduce((sum, value) => sum + (value - avg) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function coefficientOfVariation(values) {
  const avg = mean(values);
  return avg === 0 ? 0 : std(values) / avg;
}

function oneWayAnova(groups) {
  const flat = groups.flat();
  const grandMean = mean(flat);
  const ssBetween = groups.reduce((sum, group) => sum + group.length * (mean(group) - grandMean) ** 2, 0);
  const ssWithin = groups.reduce(
    (sum, group) => sum + group.reduce((inner, value) => inner + (value - mean(group)) ** 2, 0),
    0
  );
  const dfBetween = Math.max(groups.length - 1, 1);
  const dfWithin = Math.max(flat.length - groups.length, 1);
  const msBetween = ssBetween / dfBetween;
  const msWithin = ssWithin / dfWithin || 1;
  return {
    fValue: msBetween / msWithin,
    effect: ssBetween / (ssBetween + ssWithin || 1),
  };
}

function correlation(xs, ys) {
  const n = Math.min(xs.length, ys.length);
  if (!n) return 0;
  const xMean = mean(xs);
  const yMean = mean(ys);
  let numerator = 0;
  let xVariance = 0;
  let yVariance = 0;
  for (let i = 0; i < n; i += 1) {
    const dx = xs[i] - xMean;
    const dy = ys[i] - yMean;
    numerator += dx * dy;
    xVariance += dx ** 2;
    yVariance += dy ** 2;
  }
  return numerator / Math.sqrt(xVariance * yVariance || 1);
}

function quantile(values, ratio) {
  if (!values.length) return 0;
  const index = (values.length - 1) * ratio;
  const low = Math.floor(index);
  const high = Math.ceil(index);
  if (low === high) return values[low];
  return values[low] + (values[high] - values[low]) * (index - low);
}

function groupBy(items, key) {
  return items.reduce((acc, item) => {
    const groupKey = String(item[key]);
    acc[groupKey] ||= [];
    acc[groupKey].push(item);
    return acc;
  }, {});
}

function downloadCsv(filename, headers, rows) {
  const csv = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function syncWithBackend() {
  try {
    const health = await api("/health");
    state.backend.available = Boolean(health?.ok);
    state.backend.trainedModels = health?.trainedModels || [];
    state.backend.mlAvailable = Boolean(health?.mlAvailable);
    state.backend.mlError = health?.mlError || "";
    els.backendStatus.textContent = state.backend.trainedModels.length
      ? `后端在线，已加载 ${state.backend.trainedModels.join("、")} 模型。`
      : "后端在线，当前使用数据库样本与可训练模型服务。";

    const [schemesRes, datasetRes] = await Promise.all([api("/schemes"), api("/dataset")]);
    if (Array.isArray(schemesRes?.schemes) && schemesRes.schemes.length) {
      state.schemes = schemesRes.schemes;
      persist(STORAGE_KEYS.schemes, state.schemes);
    }
    if (Array.isArray(datasetRes?.rows) && datasetRes.rows.length) {
      state.dataset = datasetRes.rows;
      persist(STORAGE_KEYS.dataset, state.dataset);
    }
    if (state.auth.token) {
      try {
        const me = await api("/auth/me", { omitProject: true });
        state.auth.user = me.user;
        await loadProjects();
      } catch (error) {
        logoutUser();
      }
    } else {
      renderProjectOptions();
    }
    renderStatusStrip();
  } catch (error) {
    state.backend.available = false;
    state.backend.mlAvailable = false;
    state.backend.mlError = "";
    els.backendStatus.textContent = "未检测到后端，当前以纯前端离线模式运行。";
    renderProjectOptions();
    renderStatusStrip();
  }
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (!options.omitAuth && state.auth.token) {
    headers.Authorization = `Bearer ${state.auth.token}`;
  }
  const url = new URL(`${API_BASE}${path}`);
  if (!options.omitProject && state.auth.currentProjectId) {
    url.searchParams.set("projectId", state.auth.currentProjectId);
  }
  const response = await fetch(url, {
    headers,
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.detail || `API ${path} failed: ${response.status}`);
  }
  return data;
}

function renderStatusStrip() {
  els.currentUser.textContent = state.auth.user?.username || "未登录";
  els.currentProject.textContent = currentProjectName() || "默认项目";
  els.mlStatus.textContent = state.backend.available
    ? state.backend.mlAvailable
      ? `${state.backend.trainedModels.length ? "模型可用" : "后端在线"}`
      : state.backend.mlError || "后端在线，模型待训练"
    : "离线模式";
}

function currentProjectName() {
  return state.auth.projects.find((item) => String(item.id) === String(state.auth.currentProjectId))?.name || "";
}

function setFeedback(text, type = "") {
  if (!els.globalFeedback) return;
  els.globalFeedback.textContent = text;
  els.backendStatus.classList.remove("is-error", "is-success");
  els.authStatus.classList.remove("is-error", "is-success");
  els.projectStatus.classList.remove("is-error", "is-success");
  if (type) {
    els.backendStatus.classList.add(`is-${type}`);
    els.authStatus.classList.add(`is-${type}`);
    els.projectStatus.classList.add(`is-${type}`);
  }
}

function safeText(error) {
  return error?.message || "操作失败，请稍后重试。";
}

function buildRankingEntry(scheme, metrics) {
  const score =
    metrics.ucs * 0.28 +
    metrics.frictionAngle * 8 +
    metrics.caco3 * 12 -
    metrics.disintegrationRate * 7 -
    metrics.permeability * 6;
  return { scheme, score, metrics };
}

function firstFinite(...values) {
  for (const value of values) {
    if (Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

function loadState(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function persist(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function labelOf(key) {
  return PARAM_DEFS.find((item) => item.key === key)?.label || METRIC_DEFS.find((item) => item.key === key)?.label || key;
}

function scale(value, min, max) {
  return clamp((value - min) / (max - min), 0, 1);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function map(value, fromMin, fromMax, toMin, toMax) {
  if (fromMax === fromMin) return (toMin + toMax) / 2;
  return toMin + ((value - fromMin) / (fromMax - fromMin)) * (toMax - toMin);
}

function formatNumber(value, digits = 2) {
  return Number(value || 0).toFixed(digits).replace(/\.00$/, "");
}
