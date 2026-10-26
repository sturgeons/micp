/**
 * MICP-椰壳纤维协同固化砂土性能分析与预测系统 —— 前端工作台
 *
 * 结构：
 *   1. 常量与数据字典（与后端 micp/schemas.py 保持一致）
 *   2. 机理模型 JS 版（与后端 micp/mechanism.py 同一套公式，用于后端不可用时的离线回退）
 *   3. 应用状态与 DOM 引用
 *   4. 事件绑定与各功能模块（参数管理 / 预测 / 评估 / 敏感性 / 优化 / 统计 / 相关 / 图表 / 报告 / 账户）
 *   5. Canvas 绘图
 *   6. 通用工具
 */

// ---------------------------------------------------------------------------- 1. 常量
const STORAGE_KEYS = {
  schemes: "micp_schemes",
  templates: "micp_templates",
  dataset: "micp_dataset",
  authToken: "micp_auth_token",
  projectId: "micp_project_id",
};

const API_BASE = `${window.location.origin}/api`;

const PARAM_DEFS = [
  { key: "dryDensity", label: "砂土干密度", unit: "g/cm³", min: 1.2, max: 2.2, step: 0.01, value: 1.6 },
  { key: "fiberContent", label: "椰壳纤维掺量", unit: "%", min: 0, max: 1, step: 0.01, value: 0.4 },
  { key: "bacterialVolume", label: "菌液用量", unit: "mL", min: 10, max: 300, step: 1, value: 120 },
  { key: "odValue", label: "菌液 OD600", unit: "", min: 0.2, max: 3, step: 0.01, value: 1.2 },
  { key: "temperature", label: "固化温度", unit: "℃", min: 20, max: 40, step: 1, value: 30 },
  { key: "cementationDose", label: "胶结液浓度", unit: "mol/L", min: 0.1, max: 3, step: 0.01, value: 0.8 },
  { key: "fixationVolume", label: "胶结液用量", unit: "mL", min: 10, max: 300, step: 1, value: 90 },
  { key: "cycles", label: "固化次数", unit: "次", min: 1, max: 10, step: 1, value: 4, integer: true },
];

const METRIC_DEFS = [
  { key: "ucs", label: "无侧限抗压强度", unit: "kPa", higherIsBetter: true },
  { key: "postDryDensity", label: "固化后干密度", unit: "g/cm³", higherIsBetter: true },
  { key: "disintegrationRate", label: "浸水崩解率", unit: "%", higherIsBetter: false },
  { key: "permeability", label: "渗透系数", unit: "×10⁻⁴ cm/s", higherIsBetter: false },
  { key: "frictionAngle", label: "内摩擦角", unit: "°", higherIsBetter: true },
  { key: "cohesion", label: "黏聚力", unit: "kPa", higherIsBetter: true },
  { key: "caco3", label: "碳酸钙含量", unit: "%", higherIsBetter: true },
];

const OBJECTIVE_DEFS = [
  { key: "ucs", label: "无侧限抗压强度（越大越好）", value: 30 },
  { key: "disintegrationRate", label: "浸水崩解率（越小越好）", value: 15 },
  { key: "permeability", label: "渗透系数（越小越好）", value: 10 },
  { key: "caco3", label: "碳酸钙含量（越大越好）", value: 10 },
  { key: "cohesion", label: "黏聚力（越大越好）", value: 5 },
  { key: "frictionAngle", label: "内摩擦角（越大越好）", value: 5 },
  { key: "cost", label: "相对成本指数（越小越好）", value: 25 },
];

const MODEL_LABELS = {
  ensemble: "随机森林残差模型",
  gbrt: "梯度提升残差模型",
  bp: "BP 神经网络残差模型",
  mechanism: "纯机理模型",
};

const defaultSchemes = [
  { schemeName: "基准方案 A", dryDensity: 1.6, fiberContent: 0, bacterialVolume: 120, odValue: 1.2, temperature: 30, cementationDose: 0.8, fixationVolume: 90, cycles: 4 },
  { schemeName: "纤维增韧方案 B", dryDensity: 1.6, fiberContent: 0.4, bacterialVolume: 120, odValue: 1.2, temperature: 30, cementationDose: 0.8, fixationVolume: 90, cycles: 4 },
  { schemeName: "高胶结方案 C", dryDensity: 1.64, fiberContent: 0.4, bacterialVolume: 150, odValue: 1.5, temperature: 32, cementationDose: 1.2, fixationVolume: 120, cycles: 6 },
  { schemeName: "低成本方案 D", dryDensity: 1.58, fiberContent: 0.2, bacterialVolume: 80, odValue: 1.0, temperature: 28, cementationDose: 0.5, fixationVolume: 70, cycles: 3 },
];

// ---------------------------------------------------------------------------- 2. 机理模型（JS 版）
const MECH = {
  Gs: 2.65, V: 96, rhoC: 2.71, Mw: 100.09,
  KB: 50, Topt: 30, Tsig: 9, Tfloor: 0.25,
  etaMax: 0.85, kClog: 0.03, clogExp: 3, uScale: 2.4, uFloor: 0.35, inhOnset: 0.75, inhSigma: 1.8,
  fOpt: 0.4, fClusterThr: 0.75, fClusterPen: 0.45,
  ucsA: 34, ucsB: 1.08, ucsRhoExp: 2.0, ucsFiber: 0.35,
  cBase: 6, cPerCaco3: 3, cFiber: 10,
  phiBase: 26, phiRho: 10, phiLog: 2, phiFiber: 1.5,
  kRef: 9, nRef: 0.4, kFiber: 0.1,
  dBase: 42, dDecay: 3.6, dFiber: 0.3, dFloor: 1.5,
};

function mechanismFeatures(s) {
  const rho = Number(s.dryDensity);
  const fiber = Number(s.fiberContent);
  const vb = Number(s.bacterialVolume);
  const od = Number(s.odValue);
  const temp = Number(s.temperature);
  const conc = Number(s.cementationDose);
  const vf = Number(s.fixationVolume);
  const cycles = Math.max(1, Math.round(Number(s.cycles)));

  const effectiveBacteria = vb * od;
  const saturation = effectiveBacteria / (MECH.KB + effectiveBacteria);
  const temperatureFactor = MECH.Tfloor + (1 - MECH.Tfloor) * Math.exp(-(((temp - MECH.Topt) / MECH.Tsig) ** 2));
  const initialPorosity = clamp(1 - rho / MECH.Gs, 0.05, 0.6);
  const poreVolume = MECH.V * initialPorosity;
  const liquidUtilization = clamp((MECH.uScale * poreVolume) / Math.max(vf, 1e-6), MECH.uFloor, 1);
  const inhibition = Math.exp(-((Math.max(conc - MECH.inhOnset, 0) / MECH.inhSigma) ** 2));
  const calciumPerCycle = (conc * vf) / 1000;
  const perCycleEfficiency = MECH.etaMax * saturation * temperatureFactor * liquidUtilization * inhibition;
  let mass = 0;
  let filling = 0;
  for (let k = 0; k < cycles; k += 1) {
    const eff = perCycleEfficiency * (1 - filling) ** MECH.clogExp * Math.exp(-MECH.kClog * k);
    mass += calciumPerCycle * MECH.Mw * eff;
    filling = clamp(mass / MECH.rhoC / Math.max(poreVolume, 1e-6), 0, 0.95);
  }
  const dryMass = rho * MECH.V;
  const caco3 = (mass / dryMass) * 100;
  const calciumSupply = calciumPerCycle * cycles;
  const conversionEfficiency = mass / Math.max(calciumSupply * MECH.Mw, 1e-9);
  const ratio = fiber / MECH.fOpt;
  let fiberBridging = ratio * Math.exp(1 - ratio);
  const over = clamp((fiber - MECH.fClusterThr) / (1 - MECH.fClusterThr), 0, 1);
  fiberBridging *= 1 - MECH.fClusterPen * over;
  return {
    effectiveBacteria,
    temperatureFactor,
    calciumSupply,
    conversionEfficiency,
    fiberBridging,
    initialPorosity,
    poreFillingRatio: filling,
    liquidUtilization,
    theoreticalCaco3: caco3,
    saturation,
  };
}

function mechanismBaseline(s) {
  const f = mechanismFeatures(s);
  const rho = Number(s.dryDensity);
  const caco3 = f.theoreticalCaco3;
  const kc = (n) => n ** 3 / Math.max(1 - n, 1e-6) ** 2;
  const nAfter = f.initialPorosity * (1 - f.poreFillingRatio);
  const kRefLocal = (MECH.kRef * kc(f.initialPorosity)) / kc(MECH.nRef);
  return {
    ucs: MECH.ucsA * Math.max(caco3, 0.05) ** MECH.ucsB * (rho / 1.6) ** MECH.ucsRhoExp * (1 + MECH.ucsFiber * f.fiberBridging),
    postDryDensity: rho * (1 + caco3 / 100),
    disintegrationRate: Math.max(MECH.dBase * Math.exp(-MECH.dDecay * f.poreFillingRatio) * (1 - MECH.dFiber * f.fiberBridging), MECH.dFloor),
    permeability: ((kRefLocal * kc(nAfter)) / kc(f.initialPorosity)) * (1 - MECH.kFiber * f.fiberBridging),
    frictionAngle: MECH.phiBase + MECH.phiRho * (rho - 1.4) + MECH.phiLog * Math.log1p(caco3) + MECH.phiFiber * f.fiberBridging,
    cohesion: MECH.cBase + MECH.cPerCaco3 * caco3 + MECH.cFiber * f.fiberBridging,
    caco3,
  };
}

function offlineSensitivity(scheme) {
  const base = mechanismBaseline(scheme);
  const ranking = PARAM_DEFS.map((param) => {
    let span = (param.max - param.min) * 0.1;
    if (param.integer) span = Math.max(1, Math.round(span));
    const x0 = Number(scheme[param.key]);
    const hi = Math.min(param.max, x0 + span);
    const lo = Math.max(param.min, x0 - span);
    const plus = mechanismBaseline({ ...scheme, [param.key]: hi });
    const minus = mechanismBaseline({ ...scheme, [param.key]: lo });
    const xRef = Math.abs(x0) > 1e-9 ? x0 : hi - lo || 1;
    const elasticity = {};
    METRIC_DEFS.forEach((metric) => {
      const yRef = Math.abs(base[metric.key]) > 1e-9 ? base[metric.key] : 1;
      const dy = (plus[metric.key] - minus[metric.key]) / yRef;
      const dx = (hi - lo) / xRef || 1;
      elasticity[metric.key] = dy / dx;
    });
    const raw = mean(Object.values(elasticity).map(Math.abs));
    return { key: param.key, label: param.label, raw, elasticity };
  });
  const total = ranking.reduce((sum, item) => sum + item.raw, 0) || 1;
  return ranking
    .map((item) => ({ ...item, score: item.raw / total }))
    .sort((a, b) => b.score - a.score);
}

function offlineMechanismNotes(scheme) {
  const f = mechanismFeatures(scheme);
  const b = mechanismBaseline(scheme);
  return [
    { title: "菌液活性", text: `有效菌量指数 ${formatNumber(f.effectiveBacteria, 1)} mL·OD，脲酶饱和度 ${formatNumber(f.saturation)}，温度活性因子 ${formatNumber(f.temperatureFactor)}。` },
    { title: "钙源转化", text: `累计钙源 ${formatNumber(f.calciumSupply, 3)} mol，平均转化效率 ${formatNumber(f.conversionEfficiency)}，理论碳酸钙含量 ${formatNumber(f.theoreticalCaco3)}%。` },
    { title: "孔隙填充", text: `初始孔隙率 ${formatNumber(f.initialPorosity, 3)}，孔隙填充率 ${formatNumber(f.poreFillingRatio * 100, 1)}%，灌注液利用率 ${formatNumber(f.liquidUtilization)}。` },
    { title: "纤维桥接", text: `纤维掺量 ${formatNumber(scheme.fiberContent)}%，桥接因子 ${formatNumber(f.fiberBridging)}（最优掺量 ${MECH.fOpt}%）。` },
    { title: "机理基线", text: `UCS ${formatNumber(b.ucs, 0)} kPa、崩解率 ${formatNumber(b.disintegrationRate, 1)}%、渗透系数 ${formatNumber(b.permeability)}×10⁻⁴ cm/s。` },
  ];
}

function predictOffline(scheme) {
  const baseline = mechanismBaseline(scheme);
  const rounded = {};
  METRIC_DEFS.forEach((m) => {
    rounded[m.key] = Number(baseline[m.key].toFixed(4));
  });
  const zero = Object.fromEntries(METRIC_DEFS.map((m) => [m.key, 0]));
  return {
    model: "mechanism",
    modelLabel: MODEL_LABELS.mechanism,
    fallback: true,
    metrics: rounded,
    decomposition: { baseline: rounded, correction: zero, final: rounded },
    mechanism: offlineMechanismNotes(scheme),
    sensitivity: offlineSensitivity(scheme),
    sensitivityMethod: "OAT 弹性系数（前端机理模型）",
  };
}

function buildOfflineDataset(count = 16) {
  const rng = seededRandom(20260623);
  const rows = [];
  for (let i = 0; i < count; i += 1) {
    const scheme = {
      dryDensity: Number((1.5 + rng() * 0.25).toFixed(2)),
      fiberContent: [0, 0.2, 0.4, 0.6][i % 4],
      bacterialVolume: Math.round((80 + rng() * 120) / 5) * 5,
      odValue: Number((0.8 + rng() * 1.2).toFixed(2)),
      temperature: Math.round(24 + rng() * 12),
      cementationDose: Number((0.5 + rng() * 1.0).toFixed(2)),
      fixationVolume: Math.round((60 + rng() * 120) / 5) * 5,
      cycles: 2 + Math.floor(rng() * 6),
    };
    const base = mechanismBaseline(scheme);
    const row = { sampleId: `L${String(i + 1).padStart(2, "0")}`, ...scheme };
    METRIC_DEFS.forEach((m) => {
      const noise = 1 + (rng() - 0.5) * 0.1;
      row[m.key] = Number((base[m.key] * noise).toFixed(m.key === "ucs" ? 0 : 3));
    });
    rows.push(row);
  }
  return rows;
}

// ---------------------------------------------------------------------------- 3. 状态与 DOM
const state = {
  schemes: loadState(STORAGE_KEYS.schemes, defaultSchemes),
  templates: loadState(STORAGE_KEYS.templates, []),
  dataset: loadState(STORAGE_KEYS.dataset, buildOfflineDataset()),
  lastPrediction: null,
  lastAnalysis: null,
  lastEvaluation: null,
  lastOptimization: null,
  lastCorrelation: null,
  lastMorris: null,
  lastPdp: null,
  ranking: [],
  modelHistory: [],
  backend: {
    available: false,
    mlAvailable: false,
    mlError: "",
    trainedModels: [],
    models: [],
    minTrainSamples: 8,
  },
  auth: {
    token: localStorage.getItem(STORAGE_KEYS.authToken) || "",
    user: null,
    projects: [],
    currentProjectId: localStorage.getItem(STORAGE_KEYS.projectId) || "",
  },
};

const $ = (selector) => document.querySelector(selector);
const els = {
  form: $("#parameter-form"),
  paramInputs: $("#param-inputs"),
  validation: $("#validation-message"),
  validationReport: $("#validation-report"),
  schemeTable: $("#scheme-table"),
  templateSelect: $("#template-select"),
  predictionScheme: $("#prediction-scheme"),
  predictionModel: $("#prediction-model"),
  predictionModelPill: $("#prediction-model-pill"),
  predictionGrid: $("#prediction-grid"),
  decompositionTable: $("#decomposition-table"),
  mechanismNotes: $("#mechanism-notes"),
  sensitivityList: $("#sensitivity-list"),
  recommendation: $("#recommendation"),
  schemeRanking: $("#scheme-ranking"),
  evaluationTable: $("#evaluation-table"),
  evaluationNote: $("#evaluation-note"),
  evaluationPill: $("#evaluation-pill"),
  metricEvaluationTable: $("#metric-evaluation-table"),
  trainingMetrics: $("#training-metrics"),
  modelHistoryTable: $("#model-history-table"),
  pdpParam: $("#pdp-param"),
  pdpMetric: $("#pdp-metric"),
  pdpCanvas: $("#pdp-canvas"),
  morrisTrajectories: $("#morris-trajectories"),
  morrisMetric: $("#morris-metric"),
  morrisMeta: $("#morris-meta"),
  morrisTable: $("#morris-table"),
  weightSliders: $("#weight-sliders"),
  restrictToData: $("#restrict-to-data"),
  optimizerMeta: $("#optimizer-meta"),
  optimizerTable: $("#optimizer-table"),
  paretoCanvas: $("#pareto-canvas"),
  datasetTable: $("#dataset-table"),
  datasetMeta: $("#dataset-meta"),
  anovaFactor: $("#anova-factor"),
  anovaResponse: $("#anova-response"),
  statsSummary: $("#stats-summary"),
  analysisDetail: $("#analysis-detail"),
  correlationCanvas: $("#correlation-canvas"),
  correlationTable: $("#correlation-table"),
  chartX: $("#chart-x"),
  chartY: $("#chart-y"),
  chartType: $("#chart-type"),
  chartCanvas: $("#chart-canvas"),
  reportFrame: $("#report-frame"),
  reportPreview: $("#report-preview"),
  reportMeta: $("#report-meta"),
  schemeCount: $("#scheme-count"),
  datasetCount: $("#dataset-count"),
  bestR2: $("#best-r2"),
  backendStatus: $("#backend-status"),
  currentUser: $("#current-user"),
  currentProject: $("#current-project"),
  mlStatus: $("#ml-status"),
  globalFeedback: $("#global-feedback"),
  authUsername: $("#auth-username"),
  authPassword: $("#auth-password"),
  authStatus: $("#auth-status"),
  projectName: $("#project-name"),
  projectDescription: $("#project-description"),
  projectSelect: $("#project-select"),
  projectStatus: $("#project-status"),
};

init();

async function init() {
  renderParamInputs();
  renderWeightSliders();
  bindEvents();
  await syncWithBackend();
  hydrateSelectors();
  renderAll();
}

// ---------------------------------------------------------------------------- 4. 事件
function bindEvents() {
  els.form.addEventListener("submit", handleSchemeSave);
  $("#save-template").addEventListener("click", saveTemplate);
  $("#apply-template").addEventListener("click", applyTemplate);
  $("#export-params").addEventListener("click", exportSchemes);
  $("#batch-import").addEventListener("change", (event) => importCsv(event, "scheme"));
  $("#dataset-import").addEventListener("change", (event) => importCsv(event, "sample"));
  $("#export-dataset").addEventListener("click", exportDataset);
  $("#seed-dataset").addEventListener("click", seedDemo);
  $("#seed-demo").addEventListener("click", seedDemo);
  $("#run-prediction").addEventListener("click", runPrediction);
  $("#compare-schemes").addEventListener("click", compareSchemes);
  $("#train-models").addEventListener("click", trainModels);
  $("#train-models-2").addEventListener("click", trainModels);
  $("#evaluate-models").addEventListener("click", evaluateModels);
  $("#run-pdp").addEventListener("click", runPartialDependence);
  $("#run-morris").addEventListener("click", runMorris);
  $("#run-optimizer").addEventListener("click", runOptimizer);
  $("#run-analysis").addEventListener("click", runAnalysis);
  $("#run-correlation").addEventListener("click", runCorrelation);
  $("#render-chart").addEventListener("click", renderChart);
  $("#export-report").addEventListener("click", exportReport);
  $("#export-report-2").addEventListener("click", exportReport);
  $("#preview-report").addEventListener("click", previewReport);
  $("#register-user").addEventListener("click", registerUser);
  $("#login-user").addEventListener("click", loginUser);
  $("#logout-user").addEventListener("click", logoutUser);
  $("#create-project").addEventListener("click", createProject);
  $("#refresh-projects").addEventListener("click", () => loadProjects());
  els.projectSelect.addEventListener("change", switchProject);
  els.pdpMetric.addEventListener("change", () => state.lastPdp && drawPdpChart());
  els.morrisMetric.addEventListener("change", () => state.lastMorris && renderMorris());
}

// ---------------------------------------------------------------------------- 参数管理
function renderParamInputs() {
  els.paramInputs.innerHTML = PARAM_DEFS.map(
    (p) => `
      <label>
        <span>${p.label}${p.unit ? ` (${p.unit})` : ""} <em class="range-hint">${p.min}~${p.max}</em></span>
        <input name="${p.key}" type="number" step="${p.step}" min="${p.min}" max="${p.max}" value="${p.value}" required />
      </label>`
  ).join("");
}

function readForm() {
  const scheme = Object.fromEntries(new FormData(els.form).entries());
  PARAM_DEFS.forEach((p) => {
    scheme[p.key] = Number(scheme[p.key]);
  });
  return scheme;
}

function validateScheme(scheme) {
  if (!scheme.schemeName?.trim()) return "方案名称不能为空。";
  for (const param of PARAM_DEFS) {
    const value = Number(scheme[param.key]);
    if (!Number.isFinite(value)) return `${param.label} 必须为数值。`;
    if (value < param.min || value > param.max) {
      return `${param.label} ${value} 超出范围 ${param.min}~${param.max}${param.unit}。`;
    }
  }
  return "";
}

async function handleSchemeSave(event) {
  event.preventDefault();
  const scheme = readForm();
  const error = validateScheme(scheme);
  if (error) {
    els.validation.textContent = error;
    setFeedback(error, "error");
    return;
  }
  try {
    await persistSchemes([scheme]);
    els.validation.textContent = `方案「${scheme.schemeName}」已保存。`;
    setFeedback(`方案「${scheme.schemeName}」已保存到当前项目。`, "success");
    hydrateSelectors();
    renderAll();
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

async function persistSchemes(schemes) {
    if (state.backend.available) {
    const result = await api("/schemes", { method: "POST", body: JSON.stringify({ schemes }) });
    state.schemes = result.schemes;
    renderValidationReport({ warnings: result.warnings || [], errors: [], accepted: schemes.length, total: schemes.length });
  } else {
    schemes.forEach((scheme) => {
      const index = state.schemes.findIndex((item) => item.schemeName === scheme.schemeName);
      if (index >= 0) state.schemes[index] = scheme;
      else state.schemes.unshift(scheme);
    });
  }
    persist(STORAGE_KEYS.schemes, state.schemes);
}

function saveTemplate() {
  const scheme = readForm();
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
  setFeedback(`模板「${template.templateName}」已保存，可跨项目复用。`, "success");
}

function applyTemplate() {
  const template = state.templates.find((item) => item.templateName === els.templateSelect.value);
  if (!template) {
    setFeedback("请先选择一个模板。", "error");
    return;
  }
  Object.entries(template).forEach(([key, value]) => {
    if (key === "templateName") return;
    const field = els.form.elements.namedItem(key);
    if (field) field.value = value;
  });
  els.validation.textContent = `模板「${template.templateName}」已应用。`;
  setFeedback(`模板「${template.templateName}」已回填到表单。`, "success");
}

function importCsv(event, kind) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const text = String(reader.result || "");
      let validation;
        if (state.backend.available) {
        validation = await api("/dataset/validate", { method: "POST", body: JSON.stringify({ kind, csv: text }) });
      } else {
        validation = validateLocally(parseCsv(text), kind);
      }
      renderValidationReport(validation);
      if (!validation.accepted) {
        setFeedback(`CSV 中没有通过校验的行（共 ${validation.total} 行）。`, "error");
        return;
      }
      if (kind === "scheme") {
        await persistSchemes(validation.valid);
        els.validation.textContent = `已导入 ${validation.accepted} 组参数方案，跳过 ${validation.rejected} 组。`;
      } else {
        state.dataset = validation.valid;
        if (state.backend.available) {
          const result = await api("/dataset", { method: "POST", body: JSON.stringify({ rows: validation.valid, skipInvalid: true }) });
          state.dataset = result.rows;
        }
        persist(STORAGE_KEYS.dataset, state.dataset);
        state.lastAnalysis = null;
        state.lastEvaluation = null;
        els.datasetMeta.textContent = `已导入 ${validation.accepted} 条历史样本，跳过 ${validation.rejected} 条；请重新训练模型。`;
      }
      setFeedback(`CSV 导入完成：接受 ${validation.accepted} 行，拒绝 ${validation.rejected} 行。`, validation.rejected ? "error" : "success");
      hydrateSelectors();
      renderAll();
    } catch (err) {
      setFeedback(safeText(err), "error");
    } finally {
      event.target.value = "";
    }
  };
  reader.readAsText(file, "utf-8");
}

function validateLocally(rows, kind) {
  const errors = [];
  const warnings = [];
  const valid = [];
  rows.forEach((raw, i) => {
    const row = {};
    Object.entries(raw).forEach(([k, v]) => {
      row[k.trim()] = v === "" ? "" : Number.isFinite(Number(v)) ? Number(v) : v;
    });
    const nameKey = kind === "scheme" ? "schemeName" : "sampleId";
    row[nameKey] ||= kind === "scheme" ? `方案${i + 1}` : `S${String(i + 1).padStart(2, "0")}`;
    let ok = true;
    PARAM_DEFS.forEach((p) => {
      const value = Number(row[p.key]);
      if (!Number.isFinite(value)) {
        errors.push({ row: i + 1, field: p.key, message: `${p.label}缺失或不是数值` });
        ok = false;
      } else if (value < p.min || value > p.max) {
        errors.push({ row: i + 1, field: p.key, message: `${p.label} ${value} 超出范围 [${p.min}, ${p.max}]` });
        ok = false;
      }
    });
    if (kind === "sample") {
      METRIC_DEFS.forEach((m) => {
        if (!Number.isFinite(Number(row[m.key]))) {
          errors.push({ row: i + 1, field: m.key, message: `${m.label}缺失或不是数值` });
          ok = false;
        }
      });
    }
    if (ok) valid.push(row);
  });
  return { kind, total: rows.length, accepted: valid.length, rejected: rows.length - valid.length, valid, errors, warnings };
}

function renderValidationReport(validation) {
  if (!validation) {
    els.validationReport.innerHTML = "";
    return;
  }
  const errors = validation.errors || [];
  const warnings = validation.warnings || [];
  const unknown = validation.unknownHeaders || [];
  if (!errors.length && !warnings.length && !unknown.length) {
    els.validationReport.innerHTML = `<p class="message is-success">校验通过：${validation.accepted}/${validation.total} 行有效。</p>`;
    return;
  }
  const rows = [
    ...errors.map((e) => `<tr class="row-error"><td>${e.row}</td><td>${e.field}</td><td>错误</td><td>${e.message}</td></tr>`),
    ...warnings.map((w) => `<tr class="row-warning"><td>${w.row || "-"}</td><td>${w.field}</td><td>警告</td><td>${w.message}</td></tr>`),
  ];
  els.validationReport.innerHTML = `
    <p class="message">校验结果：接受 ${validation.accepted} 行，拒绝 ${validation.rejected} 行${unknown.length ? `；未识别表头：${unknown.join("、")}` : ""}。</p>
    <div class="table-wrap compact">
      <table>
        <thead><tr><th>行</th><th>字段</th><th>级别</th><th>说明</th></tr></thead>
        <tbody>${rows.slice(0, 40).join("")}</tbody>
      </table>
    </div>`;
}

// ---------------------------------------------------------------------------- 预测
async function runPrediction() {
  try {
    const scheme = currentScheme();
    if (!scheme) {
      setFeedback("当前没有可用于预测的方案。", "error");
      return;
    }
    const model = els.predictionModel.value;
    let prediction = predictOffline(scheme);
    if (state.backend.available && state.backend.mlAvailable) {
      prediction = await api("/predict", { method: "POST", body: JSON.stringify({ scheme, model }) });
    }
    state.lastPrediction = { ...prediction, schemeName: scheme.schemeName, requestedModel: model };
    renderPrediction();
    const label = prediction.modelLabel || MODEL_LABELS[prediction.model] || model;
    setFeedback(
      prediction.fallback && model !== "mechanism"
        ? `样本不足或模型未训练，方案「${scheme.schemeName}」已使用纯机理模型预测。`
        : `已完成方案「${scheme.schemeName}」的预测（${label}）。`,
      prediction.fallback && model !== "mechanism" ? "error" : "success"
    );
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function currentScheme() {
  return state.schemes.find((item) => item.schemeName === els.predictionScheme.value) || state.schemes[0];
}

function renderPrediction() {
  if (!state.schemes.length) {
    els.predictionGrid.innerHTML = '<p class="message">请先录入方案后再执行预测。</p>';
    els.sensitivityList.innerHTML = "";
    els.decompositionTable.innerHTML = "";
    els.mechanismNotes.innerHTML = "";
    return;
  }
  if (!state.lastPrediction) {
    state.lastPrediction = { ...predictOffline(state.schemes[0]), schemeName: state.schemes[0].schemeName };
  }
  const p = state.lastPrediction;
  els.predictionModelPill.textContent = `${p.modelLabel || MODEL_LABELS[p.model] || p.model}${p.fallback ? "（回退）" : ""}`;
  els.predictionGrid.innerHTML = METRIC_DEFS.map(
    (metric) => `
      <div class="result-item">
        <span>${metric.label}</span>
        <strong>${formatNumber(p.metrics[metric.key])} <small>${metric.unit}</small></strong>
      </div>`
  ).join("");
  const d = p.decomposition || {};
  els.decompositionTable.innerHTML = METRIC_DEFS.map((metric) => {
    const corr = d.correction?.[metric.key] ?? 0;
    return `
      <tr>
        <td>${metric.label}</td>
        <td>${formatNumber(d.baseline?.[metric.key])}</td>
        <td class="${corr >= 0 ? "pos" : "neg"}">${corr >= 0 ? "+" : ""}${formatNumber(corr, 3)}</td>
        <td><strong>${formatNumber(p.metrics[metric.key])}</strong></td>
      </tr>`;
  }).join("");
  els.mechanismNotes.innerHTML = (p.mechanism || []).map((n) => `<li><strong>${n.title}：</strong>${n.text}</li>`).join("");
  els.sensitivityList.innerHTML = (p.sensitivity || [])
    .map((item) => {
      const e = item.elasticity || {};
      return `<li><span class="sens-label">${item.label}</span><span class="sens-bar"><i style="width:${Math.min(100, item.score * 100 * 1.6)}%"></i></span><span class="sens-value">${formatNumber(item.score * 100, 1)}%</span><small>E(UCS)=${formatNumber(e.ucs, 2)}</small></li>`;
    })
    .join("");
}

async function compareSchemes() {
  if (!state.schemes.length) {
    setFeedback("请先录入或导入方案。", "error");
    return;
  }
  try {
    let ranking;
    if (state.backend.available && state.backend.mlAvailable) {
      const result = await api("/schemes/rank", { method: "POST", body: JSON.stringify({ model: els.predictionModel.value, weights: readWeights() }) });
      ranking = result.ranking;
    } else {
      ranking = rankLocally(state.schemes);
    }
    state.ranking = ranking;
    const best = ranking[0];
    els.recommendation.innerHTML = `
      <h4>综合评分最优方案</h4>
      <p><strong>${best.schemeName}</strong> 得分 ${formatNumber(best.score, 3)}：预测 UCS ${formatNumber(best.metrics.ucs, 0)} kPa、崩解率 ${formatNumber(best.metrics.disintegrationRate, 1)}%、相对成本 ${formatNumber(best.cost, 1)}。评分采用与配比优化器相同的加权归一化目标函数。</p>`;
    renderSchemeRanking();
    setFeedback("多方案综合评分完成。", "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function costIndex(s) {
  return Math.max(1, Number(s.cycles)) * ((0.4 * Number(s.bacterialVolume) * Number(s.odValue)) / 900 + (0.6 * Number(s.cementationDose) * Number(s.fixationVolume)) / 900) * 100;
}

function rankLocally(schemes) {
  const weights = normalizeWeights(readWeights());
  const rows = schemes.map((scheme) => ({ scheme, schemeName: scheme.schemeName, metrics: mechanismBaseline(scheme), cost: costIndex(scheme), score: 0 }));
  if (rows.length > 1) {
    Object.entries(weights).forEach(([key, w]) => {
      if (w <= 0) return;
      const values = rows.map((r) => (key === "cost" ? r.cost : r.metrics[key]));
      const lo = Math.min(...values);
      const hi = Math.max(...values);
      if (hi - lo < 1e-12) return;
      const higher = key === "cost" ? false : METRIC_DEFS.find((m) => m.key === key)?.higherIsBetter;
      rows.forEach((r, i) => {
        r.score += w * (higher ? (values[i] - lo) / (hi - lo) : (hi - values[i]) / (hi - lo));
      });
    });
  } else if (rows.length === 1) {
    rows[0].score = 1;
  }
  return rows.sort((a, b) => b.score - a.score).map((r, i) => ({ ...r, rank: i + 1 }));
}

function renderSchemeRanking() {
  if (!state.ranking.length) {
    els.schemeRanking.innerHTML = '<p class="message">点击“方案综合评分”后显示排序结果。</p>';
    return;
  }
  els.schemeRanking.innerHTML = `
    <table>
      <thead><tr><th>#</th><th>方案</th><th>得分</th><th>UCS</th><th>崩解率</th><th>成本</th></tr></thead>
      <tbody>
        ${state.ranking
          .map(
            (item) => `<tr><td>${item.rank}</td><td>${item.schemeName}</td><td>${formatNumber(item.score, 3)}</td><td>${formatNumber(item.metrics.ucs, 0)}</td><td>${formatNumber(item.metrics.disintegrationRate, 1)}%</td><td>${formatNumber(item.cost, 1)}</td></tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

// ---------------------------------------------------------------------------- 训练与评估
async function trainModels() {
  if (!requireBackend("模型训练")) return;
  try {
    setFeedback("正在训练 3 个学习器并执行交叉验证，请稍候...", "");
    els.evaluationPill.textContent = "训练中…";
    const result = await api("/train", { method: "POST" });
    state.backend.trainedModels = result.trainedModels || [];
    if (!state.backend.trainedModels.length) {
      setFeedback(`样本数 ${result.sampleCount} 不足 ${state.backend.minTrainSamples} 条，未训练学习器。`, "error");
      els.evaluationPill.textContent = "样本不足";
      return;
    }
    await Promise.all([loadModelHistory(), evaluateModels(true)]);
    await syncHealth();
    renderTrainingMetrics();
    setFeedback(`模型训练完成（${state.backend.trainedModels.join("、")}），推荐模型：${result.recommended || "-"}。`, "success");
    if (result.recommended) els.predictionModel.value = result.recommended;
    await runPrediction();
  } catch (err) {
    els.evaluationPill.textContent = "失败";
    setFeedback(safeText(err), "error");
  }
}

async function evaluateModels(silent = false) {
  if (!requireBackend("交叉验证评估")) return;
  try {
    if (!silent) setFeedback("正在执行交叉验证...", "");
    els.evaluationPill.textContent = "评估中…";
    state.lastEvaluation = await api("/models/evaluate", { method: "POST" });
    renderEvaluation();
    if (!silent) setFeedback(`交叉验证完成，推荐模型：${state.lastEvaluation.recommended}。`, "success");
  } catch (err) {
    els.evaluationPill.textContent = "失败";
    setFeedback(safeText(err), "error");
  }
}

function renderEvaluation() {
  const ev = state.lastEvaluation;
  if (!ev) {
    els.evaluationTable.innerHTML = '<tr><td colspan="7" class="muted">尚未评估。点击“仅评估”或“训练并保存模型”。</td></tr>';
    els.metricEvaluationTable.innerHTML = "";
    els.evaluationNote.textContent = "";
    return;
  }
  const reports = Object.entries(ev.reports || {});
  els.evaluationPill.textContent = `推荐：${MODEL_LABELS[ev.recommended] || ev.recommended}`;
  els.evaluationTable.innerHTML = reports
    .map(([name, r]) => {
      const v = r.validation?.overall;
      const t = r.train?.overall;
      return `<tr class="${name === ev.recommended ? "row-best" : ""}">
        <td>${MODEL_LABELS[name] || name}</td>
        <td>${r.folds || "-"}</td>
        <td>${v ? formatNumber(v.r2, 3) : "-"}</td>
        <td>${v ? formatNumber(v.rmse, 3) : "-"}</td>
        <td>${v ? `${formatNumber(v.mape, 1)}%` : "-"}</td>
        <td>${t ? formatNumber(t.r2, 3) : "-"}</td>
        <td>${formatNumber(r.baseline?.overall?.r2, 3)}</td>
      </tr>`;
    })
    .join("");
  const best = ev.reports?.[ev.recommended];
  els.evaluationNote.textContent = best?.note ? `${MODEL_LABELS[ev.recommended] || ev.recommended}：${best.note}（训练-验证 R² 差 ${formatNumber(best.overfitGap, 3)}）` : "";
  els.metricEvaluationTable.innerHTML = (best?.validation?.perMetric || [])
    .map((m) => `<tr><td>${m.label}</td><td>${formatNumber(m.r2, 3)}</td><td>${formatNumber(m.rmse, 3)}</td><td>${formatNumber(m.mae, 3)}</td><td>${formatNumber(m.mape, 1)}%</td></tr>`)
    .join("");
  const r2 = best?.validation?.overall?.r2;
  els.bestR2.textContent = Number.isFinite(r2) ? formatNumber(r2, 3) : "-";
}

async function loadModelHistory() {
  if (!state.backend.available) return;
  try {
    const result = await api("/models/history");
    state.modelHistory = result.history || [];
    state.backend.models = result.current || [];
    renderModelHistory();
  } catch (err) {
    /* 历史加载失败不影响主流程 */
  }
}

function renderModelHistory() {
  if (!state.modelHistory.length) {
    els.modelHistoryTable.innerHTML = '<tr><td colspan="5" class="muted">暂无训练记录。</td></tr>';
    return;
  }
  els.modelHistoryTable.innerHTML = state.modelHistory
    .slice(0, 15)
    .map(
      (h) => `<tr><td>${MODEL_LABELS[h.name] || h.name}</td><td>v${h.version}</td><td>${h.sampleCount}</td><td>${h.metrics?.r2 != null ? formatNumber(h.metrics.r2, 3) : "-"}</td><td>${formatTime(h.trainedAt)}</td></tr>`
    )
    .join("");
}

function renderTrainingMetrics() {
  const models = state.backend.models || [];
  if (!models.length) {
    els.trainingMetrics.innerHTML = `<div class="stats-item"><span>当前模型</span><strong>待训练</strong><span>训练后将显示各学习器的交叉验证指标</span></div>`;
    return;
  }
  els.trainingMetrics.innerHTML = models
    .map(
      (m) => `<div class="stats-item ${m.metrics?.recommended ? "is-best" : ""}">
        <span>${m.label || MODEL_LABELS[m.name] || m.name} v${m.version ?? "-"}</span>
        <strong>${m.metrics?.r2 != null ? formatNumber(m.metrics.r2, 3) : "-"}</strong>
        <span>CV RMSE ${formatNumber(m.metrics?.rmse, 3)} · ${m.sampleCount ?? "-"} 样本${m.metrics?.recommended ? " · 推荐" : ""}</span>
      </div>`
    )
    .join("");
}

// ---------------------------------------------------------------------------- 敏感性深入
async function runPartialDependence() {
  try {
    const scheme = currentScheme();
    if (!scheme) return;
    const param = els.pdpParam.value;
    if (state.backend.available && state.backend.mlAvailable) {
      state.lastPdp = await api("/sensitivity/partial", { method: "POST", body: JSON.stringify({ scheme, param, model: els.predictionModel.value }) });
    } else {
      state.lastPdp = localPartialDependence(scheme, param);
    }
    drawPdpChart();
    setFeedback(`已绘制「${labelOf(param)}」的偏依赖曲线。`, "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function localPartialDependence(scheme, param) {
  const def = PARAM_DEFS.find((p) => p.key === param);
  const xs = def.integer ? Array.from({ length: def.max - def.min + 1 }, (_, i) => def.min + i) : Array.from({ length: 15 }, (_, i) => def.min + ((def.max - def.min) * i) / 14);
  const curves = Object.fromEntries(METRIC_DEFS.map((m) => [m.key, []]));
  xs.forEach((x) => {
    const y = mechanismBaseline({ ...scheme, [param]: x });
    METRIC_DEFS.forEach((m) => curves[m.key].push(y[m.key]));
  });
  const current = mechanismBaseline(scheme);
  return { param, label: def.label, unit: def.unit, x: xs, curves, current: { x: Number(scheme[param]), y: current }, fallback: true };
}

async function runMorris() {
  if (!requireBackend("Morris 全局敏感性分析")) return;
  try {
    const trajectories = Number(els.morrisTrajectories.value) || 12;
    setFeedback("正在执行 Morris 分析...", "");
    state.lastMorris = await api("/sensitivity/morris", { method: "POST", body: JSON.stringify({ trajectories, model: els.predictionModel.value }) });
    renderMorris();
    setFeedback(`Morris 分析完成，共评估 ${state.lastMorris.evaluations} 组参数组合。`, "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function renderMorris() {
  const m = state.lastMorris;
  if (!m) return;
  const metric = els.morrisMetric.value;
  const rows = metric === "overall" ? m.overall : m.byMetric?.[metric]?.effects || [];
  els.morrisMeta.textContent = `${m.method}，模型：${MODEL_LABELS[m.model] || m.model}。μ* 越大表示影响越强，σ 越大表示非线性或交互效应越显著；σ/μ* > 1 通常意味着该参数与其他参数存在显著交互。${
    metric === "overall" ? "综合视图取 7 项指标的平均，不含带符号的 μ。" : ""
  }`;
  els.morrisTable.innerHTML = rows
    .map((r) => {
      const ratio = r.muStar > 1e-9 ? r.sigma / r.muStar : 0;
      return `<tr><td>${r.label}</td><td>${formatNumber(r.muStar, 3)}</td><td>${r.mu != null ? formatNumber(r.mu, 3) : "—"}</td><td>${formatNumber(r.sigma, 3)}</td><td class="${ratio > 1 ? "neg" : ""}">${formatNumber(ratio, 2)}</td></tr>`;
    })
    .join("");
}

// ---------------------------------------------------------------------------- 配比优化
function renderWeightSliders() {
  els.weightSliders.innerHTML = OBJECTIVE_DEFS.map(
    (o) => `
      <label class="slider-row">
        <span>${o.label}</span>
        <input type="range" min="0" max="50" step="1" value="${o.value}" data-weight="${o.key}" />
        <output>${o.value}</output>
      </label>`
  ).join("");
  els.weightSliders.querySelectorAll("input[type=range]").forEach((input) => {
    input.addEventListener("input", () => {
      input.nextElementSibling.textContent = input.value;
    });
  });
}

function readWeights() {
  const weights = {};
  els.weightSliders.querySelectorAll("input[type=range]").forEach((input) => {
    weights[input.dataset.weight] = Number(input.value);
  });
  return weights;
}

function normalizeWeights(weights) {
  const total = Object.values(weights).reduce((s, v) => s + Math.max(v, 0), 0) || 1;
  return Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, Math.max(v, 0) / total]));
}

async function runOptimizer() {
  if (!requireBackend("配比优化")) return;
  try {
    setFeedback("正在执行拉丁超立方采样与局部细化...", "");
    state.lastOptimization = await api("/optimize", {
      method: "POST",
      body: JSON.stringify({ weights: readWeights(), restrictToData: els.restrictToData.checked, model: els.predictionModel.value, topN: 8 }),
    });
    renderOptimizer();
    setFeedback(`配比优化完成，共评估 ${state.lastOptimization.evaluated} 组候选。`, "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function renderOptimizer() {
  const o = state.lastOptimization;
  if (!o) {
    els.optimizerTable.innerHTML = '<tr><td colspan="12" class="muted">设置权重后点击“执行配比优化”。</td></tr>';
    return;
  }
  const bounds = o.bounds || {};
  els.optimizerMeta.textContent = `${o.method}；模型 ${MODEL_LABELS[o.model] || o.model}；${o.restrictedToData ? "搜索域限定在样本包络" : "搜索域为全参数区间"}；干密度 ${bounds.dryDensity?.join("~")} g/cm³，纤维 ${bounds.fiberContent?.join("~")}%。`;
  els.optimizerTable.innerHTML = o.topSchemes
    .map(
      (t) => `<tr class="${t.rank === 1 ? "row-best" : ""}"><td>${t.rank}</td><td>${t.params.dryDensity}</td><td>${t.params.fiberContent}</td><td>${formatNumber(t.params.bacterialVolume, 0)}</td><td>${t.params.odValue}</td><td>${formatNumber(t.params.temperature, 0)}</td><td>${t.params.cementationDose}</td><td>${formatNumber(t.params.fixationVolume, 0)}</td><td>${t.params.cycles}</td><td>${formatNumber(t.metrics.ucs, 0)}</td><td>${formatNumber(t.cost, 1)}</td><td>${formatNumber(t.score, 3)}</td></tr>`
    )
    .join("");
  drawParetoChart();
}

// ---------------------------------------------------------------------------- 统计分析
async function runAnalysis() {
  if (!state.dataset.length) {
    setFeedback("请先导入历史样本数据。", "error");
    return;
  }
  try {
    const factor = els.anovaFactor.value || "fiberContent";
    const response = els.anovaResponse.value || "ucs";
    if (state.backend.available && state.backend.mlAvailable) {
      state.lastAnalysis = await api("/analyze", { method: "POST", body: JSON.stringify({ factor, response }) });
    } else {
      state.lastAnalysis = analyzeLocally(state.dataset, factor, response);
    }
    renderAnalysis();
    setFeedback("统计分析完成。", "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function analyzeLocally(dataset, factor, response) {
  const values = dataset.map((r) => Number(r[response])).sort((a, b) => a - b);
  let clean = dataset;
  const removedDetails = [];
  if (values.length >= 4) {
    const q1 = quantile(values, 0.25);
    const q3 = quantile(values, 0.75);
    const iqr = q3 - q1;
    clean = dataset.filter((r) => {
      const ok = r[response] >= q1 - 1.5 * iqr && r[response] <= q3 + 1.5 * iqr;
      if (!ok) removedDetails.push({ sampleId: r.sampleId, metric: response, value: r[response], method: "IQR", reason: "超出 1.5 IQR" });
      return ok;
    });
  }
  const metricStats = METRIC_DEFS.map((m) => {
    const v = clean.map((r) => Number(r[m.key]));
    return { key: m.key, label: m.label, unit: m.unit, count: v.length, mean: mean(v), std: std(v), cv: coefficientOfVariation(v), min: Math.min(...v), max: Math.max(...v) };
  });
  const groups = Object.values(groupBy(clean, factor)).map((items) => items.map((r) => Number(r[response])));
  return { metricStats, removed: removedDetails.length, removedDetails, sampleSize: clean.length, rawSampleSize: dataset.length, anova: { ...oneWayAnova(groups), factor, response, groups: [] }, regression: null, factor, response };
}

function renderAnalysis() {
  const a = state.lastAnalysis;
  if (!a) {
    els.statsSummary.innerHTML = "";
    els.analysisDetail.innerHTML = "导入数据后点击“执行统计分析”，自动完成异常值检测、描述统计、方差分析与回归拟合。";
    return;
  }
  els.statsSummary.innerHTML = a.metricStats
    .map(
      (item) => `<div class="stats-item"><span>${item.label}</span><strong>${formatNumber(item.mean)}</strong><span>Std ${formatNumber(item.std)} · CV ${formatNumber(item.cv * 100, 1)}% · [${formatNumber(item.min)}, ${formatNumber(item.max)}]</span></div>`
    )
    .join("");
  const an = a.anova || {};
  const groupsHtml = an.groups?.length
    ? `<table class="mini-table"><thead><tr><th>水平</th><th>n</th><th>均值</th><th>标准差</th></tr></thead><tbody>${an.groups.map((g) => `<tr><td>${g.level}</td><td>${g.count}</td><td>${formatNumber(g.mean)}</td><td>${formatNumber(g.std)}</td></tr>`).join("")}</tbody></table>`
    : "";
  const removedHtml = a.removedDetails?.length
    ? `<p>剔除明细：${a.removedDetails.map((d) => `${d.sampleId}（${d.method}，${formatNumber(d.value)}）`).join("；")}</p>`
    : "";
  const reg = a.regression;
  const regHtml = reg?.linear
    ? `<p><strong>UCS-碳酸钙含量回归：</strong>线性 ${reg.linear.equation}（R²=${formatNumber(reg.linear.r2, 3)}，p${formatP(reg.linear.p)}）${reg.power ? `；幂函数 ${reg.power.equation}（R²=${formatNumber(reg.power.r2, 3)}）` : ""}</p>`
    : "";
  els.analysisDetail.innerHTML = `
    <p>原始样本 ${a.rawSampleSize ?? a.sampleSize} 条，IQR + Grubbs 剔除异常值 ${a.removed} 条，有效样本 ${a.sampleSize} 条。</p>
    ${removedHtml}
    <p><strong>单因素方差分析（${labelOf(an.factor || a.factor)} → ${labelOf(an.response || a.response)}）：</strong>F = ${formatNumber(an.fValue, 3)}${an.dfBetween != null ? `，df = (${an.dfBetween}, ${an.dfWithin})` : ""}${an.pValue != null ? `，p${formatP(an.pValue)}` : ""}，η² = ${formatNumber(an.eta2 ?? an.effect, 3)}。</p>
    <p class="${an.significant ? "is-success" : ""}">${an.conclusion || ""}</p>
    ${groupsHtml}
    ${regHtml}`;
}

// ---------------------------------------------------------------------------- 相关矩阵
async function runCorrelation() {
  try {
    if (state.backend.available && state.backend.mlAvailable) {
      state.lastCorrelation = await api("/statistics/correlation", { method: "POST" });
    } else {
      state.lastCorrelation = correlationLocally(state.dataset);
    }
    renderCorrelation();
    setFeedback("相关矩阵计算完成。", "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function correlationLocally(dataset) {
  const keys = [...PARAM_DEFS.map((p) => p.key), ...METRIC_DEFS.map((m) => m.key)];
  const r = keys.map((a) => keys.map((b) => correlation(dataset.map((row) => Number(row[a])), dataset.map((row) => Number(row[b])))));
  const topPairs = [];
  PARAM_DEFS.forEach((p, i) => METRIC_DEFS.forEach((m, j) => topPairs.push({ param: p.key, metric: m.key, paramLabel: p.label, metricLabel: m.label, r: r[i][PARAM_DEFS.length + j], p: null })));
  topPairs.sort((a, b) => Math.abs(b.r) - Math.abs(a.r));
  return { keys, labels: keys.map(labelOf), r, p: null, topPairs: topPairs.slice(0, 10), sampleSize: dataset.length };
}

function renderCorrelation() {
  const c = state.lastCorrelation;
  if (!c) return;
  els.correlationTable.innerHTML = c.topPairs
    .map((pair) => `<tr><td>${pair.paramLabel}</td><td>${pair.metricLabel}</td><td class="${pair.r >= 0 ? "pos" : "neg"}">${formatNumber(pair.r, 3)}</td><td>${pair.p == null ? "-" : pair.p < 0.001 ? "<0.001" : formatNumber(pair.p, 4)}</td></tr>`)
    .join("");
  drawCorrelationMatrix();
}

// ---------------------------------------------------------------------------- 渲染总控
function renderAll() {
  renderSchemes();
  renderDataset();
  renderPrediction();
  renderSchemeRanking();
  renderEvaluation();
  renderTrainingMetrics();
  renderModelHistory();
  renderOptimizer();
  renderAnalysis();
  renderChart();
  updateMetrics();
  renderStatusStrip();
  if (state.lastCorrelation) renderCorrelation();
  if (state.lastPdp) drawPdpChart();
}

function renderSchemes() {
  els.schemeTable.innerHTML = state.schemes
    .slice(0, 12)
    .map((s) => `<tr><td>${s.schemeName}</td><td>${formatNumber(s.dryDensity)}</td><td>${formatNumber(s.fiberContent)}</td><td>${formatNumber(s.cementationDose)}</td><td>${s.cycles}</td></tr>`)
    .join("");
}

function renderDataset() {
  els.datasetTable.innerHTML = state.dataset
    .slice(0, 48)
    .map(
      (r) => `<tr><td>${r.sampleId || "-"}</td><td>${formatNumber(r.fiberContent)}</td><td>${r.cycles}</td><td>${formatNumber(r.ucs, 0)}</td><td>${formatNumber(r.disintegrationRate, 1)}</td><td>${formatNumber(r.caco3)}</td></tr>`
    )
    .join("");
  els.datasetMeta.textContent ||= `当前已加载 ${state.dataset.length} 条历史样本。`;
}

function hydrateSelectors() {
  const keep = (select, options, fallback) => {
    const current = select.value;
    select.innerHTML = options;
    select.value = [...select.options].some((o) => o.value === current) ? current : fallback;
  };
  const paramOptions = PARAM_DEFS.map((p) => `<option value="${p.key}">${p.label}</option>`).join("");
  const metricOptions = METRIC_DEFS.map((m) => `<option value="${m.key}">${m.label}</option>`).join("");
  keep(els.templateSelect, `<option value="">选择模板后回填</option>${state.templates.map((t) => `<option value="${t.templateName}">${t.templateName}</option>`).join("")}`, "");
  keep(els.predictionScheme, state.schemes.map((s) => `<option value="${s.schemeName}">${s.schemeName}</option>`).join(""), state.schemes[0]?.schemeName || "");
  keep(els.chartX, paramOptions, "fiberContent");
  keep(els.chartY, metricOptions, "ucs");
  keep(els.pdpParam, paramOptions, "cementationDose");
  keep(els.pdpMetric, metricOptions, "ucs");
  keep(els.morrisMetric, `<option value="overall">综合（全部指标）</option>${metricOptions}`, "overall");
  keep(els.anovaFactor, paramOptions, "fiberContent");
  keep(els.anovaResponse, metricOptions, "ucs");
}

function updateMetrics() {
  els.schemeCount.textContent = state.schemes.length;
  els.datasetCount.textContent = state.dataset.length;
}

// ---------------------------------------------------------------------------- 报告
async function buildReportHtml() {
  if (state.backend.available && state.backend.mlAvailable) {
    const result = await api("/report", {
      method: "POST",
      body: JSON.stringify({
        prediction: state.lastPrediction,
        analysis: state.lastAnalysis,
        evaluation: state.lastEvaluation,
        optimization: state.lastOptimization,
        model: els.predictionModel.value,
      }),
    });
    return result.html;
  }
  const scheme = currentScheme();
  const p = state.lastPrediction || predictOffline(scheme);
  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>MICP 分析报告</title>
    <style>body{font-family:'Songti SC',serif;padding:40px;color:#1f2f29;line-height:1.8}h1,h2{color:#0f6a52}table{border-collapse:collapse}td,th{border:1px solid #cbd5e1;padding:4px 10px}</style></head>
    <body><h1>MICP-椰壳纤维协同固化砂土性能分析报告（离线机理模式）</h1>
    <h2>1. 方案参数</h2><table>${PARAM_DEFS.map((d) => `<tr><td>${d.label}</td><td>${scheme?.[d.key]} ${d.unit}</td></tr>`).join("")}</table>
    <h2>2. 机理解释</h2><ol>${(p.mechanism || []).map((n) => `<li><strong>${n.title}：</strong>${n.text}</li>`).join("")}</ol>
    <h2>3. 预测结果</h2><table>${METRIC_DEFS.map((m) => `<tr><td>${m.label}</td><td>${formatNumber(p.metrics[m.key])} ${m.unit}</td></tr>`).join("")}</table>
    <h2>4. 参数敏感性</h2><ol>${(p.sensitivity || []).map((s) => `<li>${s.label}：${formatNumber(s.score * 100, 1)}%</li>`).join("")}</ol>
    <p>说明：后端服务未连接，本报告由前端机理模型生成，未包含残差学习修正、交叉验证与配比优化结果。</p></body></html>`;
}

async function previewReport() {
  try {
    setFeedback("正在生成报告预览...", "");
    const html = await buildReportHtml();
    els.reportFrame.srcdoc = html;
    els.reportFrame.classList.add("is-visible");
    els.reportPreview.innerHTML = "";
    els.reportMeta.textContent = `报告上下文：${state.auth.user?.username || "匿名用户"} / ${currentProjectName() || "默认项目"} / ${MODEL_LABELS[state.lastPrediction?.model] || "未预测"} / ${new Date().toLocaleString("zh-CN")}`;
    setFeedback("报告预览已刷新。", "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

async function exportReport() {
  try {
    const html = await buildReportHtml();
    els.reportFrame.srcdoc = html;
    els.reportFrame.classList.add("is-visible");
    const blob = new Blob([html], { type: "application/msword" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `micp-report-${new Date().toISOString().slice(0, 10)}.doc`;
    link.click();
    URL.revokeObjectURL(url);
    const win = window.open("", "_blank");
    if (win) {
      win.document.write(html);
      win.document.close();
      win.focus();
      setTimeout(() => win.print(), 400);
    }
    setFeedback("分析报告已导出，并打开打印预览。", "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

// ---------------------------------------------------------------------------- 数据集操作
async function seedDemo() {
  try {
    state.lastAnalysis = null;
    state.lastEvaluation = null;
    state.lastOptimization = null;
    state.lastCorrelation = null;
    state.ranking = [];
    if (state.backend.available) {
      const result = await api("/seed", { method: "POST" });
      state.schemes = result.schemes;
      state.dataset = result.rows;
    } else {
      state.schemes = defaultSchemes;
      state.dataset = buildOfflineDataset();
    }
    persist(STORAGE_KEYS.schemes, state.schemes);
    persist(STORAGE_KEYS.dataset, state.dataset);
    els.datasetMeta.textContent = `已载入 ${state.dataset.length} 条示范样本与 ${state.schemes.length} 个方案。`;
    hydrateSelectors();
    await runPrediction();
    renderAll();
    setFeedback("示范数据已载入。", "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function exportSchemes() {
  const headers = ["schemeName", ...PARAM_DEFS.map((p) => p.key)];
  downloadCsv("micp-params.csv", headers, state.schemes.map((s) => headers.map((h) => s[h])));
  setFeedback(`已导出 ${state.schemes.length} 组参数方案。`, "success");
}

function exportDataset() {
  const headers = ["sampleId", ...PARAM_DEFS.map((p) => p.key), ...METRIC_DEFS.map((m) => m.key)];
  downloadCsv("micp-dataset.csv", headers, state.dataset.map((r) => headers.map((h) => r[h] ?? "")));
  setFeedback(`已导出 ${state.dataset.length} 条历史样本。`, "success");
}

// ---------------------------------------------------------------------------- 账户与项目
async function registerUser() {
  if (!requireBackend("账户注册")) return;
  const username = els.authUsername.value.trim();
  const password = els.authPassword.value.trim();
  if (!username || !password) {
    setFeedback("请输入用户名和密码。", "error");
    return;
  }
  try {
    const result = await api("/auth/register", { method: "POST", body: JSON.stringify({ username, password }), omitAuth: true, omitProject: true });
    els.authStatus.textContent = `用户 ${result.user.username} 注册成功，请登录。`;
    setFeedback(`用户 ${result.user.username} 注册成功。`, "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

async function loginUser() {
  if (!requireBackend("登录")) return;
  const username = els.authUsername.value.trim();
  const password = els.authPassword.value.trim();
  if (!username || !password) {
    setFeedback("请输入用户名和密码。", "error");
    return;
  }
  try {
    const result = await api("/auth/login", { method: "POST", body: JSON.stringify({ username, password }), omitAuth: true, omitProject: true });
    state.auth.token = result.token;
    state.auth.user = result.user;
    localStorage.setItem(STORAGE_KEYS.authToken, result.token);
    els.authStatus.textContent = `已登录：${result.user.username}`;
    await loadProjects();
    await syncWithBackend();
    renderAll();
    setFeedback(`欢迎，${result.user.username}。`, "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

function logoutUser() {
  state.auth = { token: "", user: null, projects: [], currentProjectId: "" };
  localStorage.removeItem(STORAGE_KEYS.authToken);
  localStorage.removeItem(STORAGE_KEYS.projectId);
  els.authStatus.textContent = "已退出登录，当前使用默认项目。";
  renderProjectOptions();
  renderStatusStrip();
  setFeedback("已退出登录。", "success");
}

async function createProject() {
  if (!state.backend.available || !state.auth.token) {
    setFeedback("请先登录后再创建项目。", "error");
    return;
  }
  const name = els.projectName.value.trim();
  if (!name) {
    setFeedback("请输入项目名称。", "error");
    return;
  }
  try {
    const result = await api("/projects", { method: "POST", body: JSON.stringify({ name, description: els.projectDescription.value.trim() }), omitProject: true });
    els.projectStatus.textContent = `项目「${result.project.name}」已创建。`;
    await loadProjects(result.project.id);
    await syncWithBackend();
    renderAll();
    setFeedback(`项目「${result.project.name}」已创建并设为当前项目。`, "success");
  } catch (err) {
    setFeedback(safeText(err), "error");
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
    if (selectedId) state.auth.currentProjectId = String(selectedId);
    else if (!state.auth.projects.some((p) => String(p.id) === String(state.auth.currentProjectId))) {
      state.auth.currentProjectId = state.auth.projects[0] ? String(state.auth.projects[0].id) : "";
    }
    localStorage.setItem(STORAGE_KEYS.projectId, state.auth.currentProjectId || "");
    renderProjectOptions();
  } catch (err) {
    setFeedback(safeText(err), "error");
  }
}

async function switchProject() {
  state.auth.currentProjectId = els.projectSelect.value;
  localStorage.setItem(STORAGE_KEYS.projectId, state.auth.currentProjectId || "");
  state.lastPrediction = null;
  state.lastAnalysis = null;
  state.lastEvaluation = null;
  state.lastOptimization = null;
  state.lastCorrelation = null;
  state.ranking = [];
  await syncWithBackend();
  hydrateSelectors();
  renderAll();
  setFeedback(`已切换到项目「${currentProjectName() || "默认项目"}」。`, "success");
}

function renderProjectOptions() {
  els.projectSelect.innerHTML = state.auth.projects.length
    ? state.auth.projects.map((p) => `<option value="${p.id}">${p.name}</option>`).join("")
    : '<option value="">默认项目</option>';
  if (state.auth.currentProjectId) els.projectSelect.value = state.auth.currentProjectId;
  els.authStatus.textContent ||= state.auth.user ? `已登录：${state.auth.user.username}` : "未登录，当前可使用默认项目。";
  renderStatusStrip();
}

// ---------------------------------------------------------------------------- 后端同步
async function syncHealth() {
  const health = await api("/health");
  state.backend.available = Boolean(health?.ok);
  state.backend.trainedModels = health?.trainedModels || [];
  state.backend.models = health?.models || [];
  state.backend.mlAvailable = Boolean(health?.mlAvailable);
  state.backend.mlError = health?.mlError || "";
  state.backend.minTrainSamples = health?.minTrainSamples || 8;
  renderBackendStatus();
  return health;
}

function renderBackendStatus() {
  if (!state.backend.available) return;
  els.backendStatus.textContent = state.backend.trainedModels.length
    ? `后端在线，当前项目已训练模型：${state.backend.trainedModels.map((m) => MODEL_LABELS[m] || m).join("、")}。`
    : "后端在线，当前项目尚未训练模型，预测将使用纯机理模型。";
  renderStatusStrip();
}

async function syncWithBackend() {
  try {
    await syncHealth();
    const [schemesRes, datasetRes] = await Promise.all([api("/schemes"), api("/dataset")]);
    state.schemes = schemesRes.schemes || [];
    state.dataset = datasetRes.rows || [];
    persist(STORAGE_KEYS.schemes, state.schemes);
    persist(STORAGE_KEYS.dataset, state.dataset);
    els.datasetMeta.textContent = `当前项目共 ${state.dataset.length} 条历史样本。`;
    await loadModelHistory();
    if (state.auth.token) {
      try {
        const me = await api("/auth/me", { omitProject: true });
        state.auth.user = me.user;
        await loadProjects();
      } catch (err) {
        logoutUser();
      }
    } else {
      renderProjectOptions();
    }
  } catch (err) {
    state.backend.available = false;
    state.backend.mlAvailable = false;
    els.backendStatus.textContent = "未检测到后端服务，当前以前端机理模型离线模式运行（不含残差学习、交叉验证与配比优化）。";
    renderProjectOptions();
  }
  renderStatusStrip();
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (!options.omitAuth && state.auth.token) headers.Authorization = `Bearer ${state.auth.token}`;
  const url = new URL(`${API_BASE}${path}`);
  if (!options.omitProject && state.auth.currentProjectId) url.searchParams.set("projectId", state.auth.currentProjectId);
  const response = await fetch(url, { headers, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    if (detail?.errors?.length) renderValidationReport(detail);
    throw new Error(data.error ? `${data.error}${typeof detail === "string" ? `：${detail}` : ""}` : `API ${path} failed: ${response.status}`);
  }
  return data;
}

function requireBackend(feature) {
  if (!state.backend.available || !state.backend.mlAvailable) {
    setFeedback(`${feature}需要后端算法服务，请先启动 Flask 服务${state.backend.mlError ? `（${state.backend.mlError}）` : ""}。`, "error");
    return false;
  }
  return true;
}

function renderStatusStrip() {
  els.currentUser.textContent = state.auth.user?.username || "未登录";
  els.currentProject.textContent = currentProjectName() || "默认项目";
  els.mlStatus.textContent = state.backend.available
    ? state.backend.mlAvailable
      ? state.backend.trainedModels.length
        ? `已训练 ${state.backend.trainedModels.length} 个模型`
        : "后端在线 · 机理模型"
      : state.backend.mlError || "算法依赖缺失"
    : "离线机理模式";
}

function currentProjectName() {
  return state.auth.projects.find((p) => String(p.id) === String(state.auth.currentProjectId))?.name || "";
}

function setFeedback(text, type = "") {
  els.globalFeedback.textContent = text;
  [els.backendStatus, els.authStatus, els.projectStatus].forEach((el) => {
    el.classList.remove("is-error", "is-success");
    if (type) el.classList.add(`is-${type}`);
  });
}

// ---------------------------------------------------------------------------- 5. Canvas 绘图
function renderChart() {
  const ctx = els.chartCanvas.getContext("2d");
  const { width, height } = els.chartCanvas;
  ctx.clearRect(0, 0, width, height);
  const chartType = els.chartType.value || "line";
  const xKey = els.chartX.value || "fiberContent";
  const yKey = els.chartY.value || "ucs";
  const data = state.dataset.filter((r) => Number.isFinite(Number(r[xKey])) && Number.isFinite(Number(r[yKey])));
  drawBackground(ctx, width, height);
  if (!data.length) {
    ctx.fillStyle = "#5c695f";
    ctx.font = "20px Manrope";
    ctx.fillText("请先导入历史数据或载入示范数据", 180, 210);
    return;
  }
  if (chartType === "bar") drawBarChart(ctx, width, height, data, xKey, yKey);
  else if (chartType === "box") drawBoxPlot(ctx, width, height, data, xKey, yKey);
  else if (chartType === "heatmap") drawHeatmap(ctx, width, height, data);
  else drawTrendChart(ctx, width, height, data, xKey, yKey);
}

function drawBackground(ctx, width, height) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "rgba(15,106,82,0.08)");
  gradient.addColorStop(1, "rgba(176,100,44,0.07)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(31,47,41,0.08)";
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

function drawAxes(ctx, width, height, xLabel, yLabel, xRange, yRange) {
  ctx.strokeStyle = "#1f2f29";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(70, height - 50);
  ctx.lineTo(width - 30, height - 50);
  ctx.moveTo(70, height - 50);
  ctx.lineTo(70, 40);
  ctx.stroke();
  ctx.fillStyle = "#1f2f29";
  ctx.font = "14px Manrope";
  ctx.fillText(xLabel, width / 2 - 40, height - 14);
  ctx.save();
  ctx.translate(16, height / 2 + 40);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();
  if (xRange && yRange) {
    ctx.font = "11px Manrope";
    ctx.fillStyle = "#5c695f";
    for (let i = 0; i <= 4; i += 1) {
      const xv = xRange[0] + ((xRange[1] - xRange[0]) * i) / 4;
      const yv = yRange[0] + ((yRange[1] - yRange[0]) * i) / 4;
      ctx.fillText(formatNumber(xv, 2), map(xv, xRange[0], xRange[1], 90, width - 60) - 12, height - 34);
      ctx.fillText(formatNumber(yv, 1), 30, map(yv, yRange[0], yRange[1], height - 80, 70) + 4);
    }
  }
}

function drawTrendChart(ctx, width, height, data, xKey, yKey) {
  const xs = data.map((r) => Number(r[xKey]));
  const ys = data.map((r) => Number(r[yKey]));
  const xRange = padRange(Math.min(...xs), Math.max(...xs));
  const yRange = padRange(Math.min(...ys), Math.max(...ys));
  drawAxes(ctx, width, height, labelOf(xKey), labelOf(yKey), xRange, yRange);
  data.forEach((r) => {
    ctx.fillStyle = "rgba(176,100,44,0.75)";
    ctx.beginPath();
    ctx.arc(map(Number(r[xKey]), xRange[0], xRange[1], 90, width - 60), map(Number(r[yKey]), yRange[0], yRange[1], height - 80, 70), 4.5, 0, Math.PI * 2);
    ctx.fill();
  });
  // 分箱均值趋势线
  const bins = Math.min(6, new Set(xs).size);
  const sorted = [...data].sort((a, b) => a[xKey] - b[xKey]);
  const perBin = Math.ceil(sorted.length / bins);
  const points = [];
  for (let i = 0; i < sorted.length; i += perBin) {
    const chunk = sorted.slice(i, i + perBin);
    points.push([mean(chunk.map((r) => Number(r[xKey]))), mean(chunk.map((r) => Number(r[yKey])))]);
  }
  ctx.strokeStyle = "#0f6a52";
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach(([x, y], i) => {
    const px = map(x, xRange[0], xRange[1], 90, width - 60);
    const py = map(y, yRange[0], yRange[1], height - 80, 70);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
  ctx.fillStyle = "#1f2f29";
  ctx.font = "12px Manrope";
  ctx.fillText(`散点：${data.length} 个样本；折线：分箱均值趋势`, 90, 30);
}

function drawBarChart(ctx, width, height, data, xKey, yKey) {
  const grouped = Object.entries(groupBy(data, xKey)).sort((a, b) => Number(a[0]) - Number(b[0])).slice(0, 8);
  const values = grouped.map(([, items]) => mean(items.map((r) => Number(r[yKey]))));
  const maxValue = Math.max(...values) * 1.1;
  drawAxes(ctx, width, height, labelOf(xKey), `${labelOf(yKey)} 均值`);
  const barWidth = (width - 140) / grouped.length;
  grouped.forEach(([group, items], index) => {
    const value = values[index];
    const x = 90 + index * barWidth + 8;
    const y = map(value, 0, maxValue, height - 50, 70);
    const gradient = ctx.createLinearGradient(0, y, 0, height - 50);
    gradient.addColorStop(0, "#0f6a52");
    gradient.addColorStop(1, "#94c7af");
    ctx.fillStyle = gradient;
    ctx.fillRect(x, y, barWidth - 16, height - 50 - y);
    ctx.fillStyle = "#1f2f29";
    ctx.font = "12px Manrope";
    ctx.fillText(`${group} (n=${items.length})`, x, height - 32);
    ctx.fillText(formatNumber(value, 1), x, y - 6);
  });
}

function drawBoxPlot(ctx, width, height, data, xKey, yKey) {
  const grouped = Object.entries(groupBy(data, xKey)).sort((a, b) => Number(a[0]) - Number(b[0])).slice(0, 8);
  const all = data.map((r) => Number(r[yKey]));
  const yRange = padRange(Math.min(...all), Math.max(...all));
  drawAxes(ctx, width, height, labelOf(xKey), labelOf(yKey), null, null);
  const spacing = (width - 140) / grouped.length;
  grouped.forEach(([group, items], index) => {
    const values = items.map((r) => Number(r[yKey])).sort((a, b) => a - b);
    const q1 = quantile(values, 0.25);
    const med = quantile(values, 0.5);
    const q3 = quantile(values, 0.75);
    const x = 100 + index * spacing;
    const sy = (v) => map(v, yRange[0], yRange[1], height - 80, 70);
    ctx.strokeStyle = "#0f6a52";
    ctx.fillStyle = "rgba(15,106,82,0.18)";
    ctx.fillRect(x, sy(q3), 40, sy(q1) - sy(q3));
    ctx.strokeRect(x, sy(q3), 40, sy(q1) - sy(q3));
    ctx.beginPath();
    ctx.moveTo(x + 20, sy(values[values.length - 1]));
    ctx.lineTo(x + 20, sy(q3));
    ctx.moveTo(x + 20, sy(q1));
    ctx.lineTo(x + 20, sy(values[0]));
    ctx.moveTo(x, sy(med));
    ctx.lineTo(x + 40, sy(med));
    ctx.stroke();
    ctx.fillStyle = "#1f2f29";
    ctx.font = "12px Manrope";
    ctx.fillText(group, x + 4, height - 32);
  });
}

function drawHeatmap(ctx, width, height, data) {
  const xParams = ["dryDensity", "fiberContent", "cementationDose", "cycles"];
  const yMetrics = ["ucs", "caco3", "cohesion", "permeability"];
  const cellW = 130;
  const cellH = 70;
  ctx.font = "13px Manrope";
  xParams.forEach((param, col) => {
    ctx.fillStyle = "#1f2f29";
    ctx.fillText(labelOf(param), 110 + col * cellW, 70);
  });
  yMetrics.forEach((metric, row) => ctx.fillText(labelOf(metric), 14, 120 + row * cellH));
  xParams.forEach((param, col) =>
  yMetrics.forEach((metric, row) => {
      const corr = correlation(data.map((r) => Number(r[param])), data.map((r) => Number(r[metric])));
      ctx.fillStyle = heatColor(corr);
      ctx.fillRect(110 + col * cellW, 90 + row * cellH, 110, 50);
      ctx.fillStyle = "#fff";
      ctx.fillText(formatNumber(corr, 2), 145 + col * cellW, 120 + row * cellH);
    })
  );
}

function drawPdpChart() {
  const pdp = state.lastPdp;
  const ctx = els.pdpCanvas.getContext("2d");
  const { width, height } = els.pdpCanvas;
  ctx.clearRect(0, 0, width, height);
  drawBackground(ctx, width, height);
  if (!pdp) return;
  const metric = els.pdpMetric.value || "ucs";
  const xs = pdp.x;
  const ys = pdp.curves[metric];
  const xRange = [Math.min(...xs), Math.max(...xs)]; // 扫描区间即参数合理区间，坐标轴不外扩
  const yRange = padRange(Math.min(...ys), Math.max(...ys));
  drawAxes(ctx, width, height, `${pdp.label}${pdp.unit ? ` (${pdp.unit})` : ""}`, labelOf(metric), xRange, yRange);
  ctx.strokeStyle = "#0f6a52";
  ctx.lineWidth = 3;
  ctx.beginPath();
  xs.forEach((x, i) => {
    const px = map(x, xRange[0], xRange[1], 90, width - 60);
    const py = map(ys[i], yRange[0], yRange[1], height - 80, 70);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
  if (pdp.current) {
    ctx.fillStyle = "#b0642c";
    ctx.beginPath();
    ctx.arc(map(pdp.current.x, xRange[0], xRange[1], 90, width - 60), map(pdp.current.y[metric], yRange[0], yRange[1], height - 80, 70), 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#1f2f29";
    ctx.font = "12px Manrope";
    ctx.fillText(`当前方案：${pdp.label}=${formatNumber(pdp.current.x, 2)} → ${labelOf(metric)} ${formatNumber(pdp.current.y[metric], 2)}${pdp.fallback ? "（机理模型）" : ""}`, 90, 30);
  }
}

function drawParetoChart() {
  const o = state.lastOptimization;
  const ctx = els.paretoCanvas.getContext("2d");
  const { width, height } = els.paretoCanvas;
  ctx.clearRect(0, 0, width, height);
  drawBackground(ctx, width, height);
  if (!o) return;
  const cloud = o.scatter || [];
  const front = o.pareto || [];
  const all = [...cloud, ...front];
  const xRange = padRange(Math.min(...all.map((p) => p.cost)), Math.max(...all.map((p) => p.cost)));
  const yRange = padRange(Math.min(...all.map((p) => p.ucs)), Math.max(...all.map((p) => p.ucs)));
  drawAxes(ctx, width, height, "相对成本指数", "UCS (kPa)", xRange, yRange);
  cloud.forEach((p) => {
    ctx.fillStyle = "rgba(37,99,235,0.35)";
    ctx.beginPath();
    ctx.arc(map(p.cost, xRange[0], xRange[1], 90, width - 60), map(p.ucs, yRange[0], yRange[1], height - 80, 70), 3.5, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.strokeStyle = "#b0642c";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  front.forEach((p, i) => {
    const px = map(p.cost, xRange[0], xRange[1], 90, width - 60);
    const py = map(p.ucs, yRange[0], yRange[1], height - 80, 70);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
  front.forEach((p) => {
    ctx.fillStyle = "#b0642c";
    ctx.beginPath();
    ctx.arc(map(p.cost, xRange[0], xRange[1], 90, width - 60), map(p.ucs, yRange[0], yRange[1], height - 80, 70), 5, 0, Math.PI * 2);
    ctx.fill();
  });
  const best = o.topSchemes?.[0];
  if (best) {
    const px = map(best.cost, xRange[0], xRange[1], 90, width - 60);
    const py = map(best.metrics.ucs, yRange[0], yRange[1], height - 80, 70);
    ctx.strokeStyle = "#0f6a52";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(px, py, 10, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.fillStyle = "#1f2f29";
  ctx.font = "12px Manrope";
  ctx.fillText(`蓝点：候选配比（抽样 ${cloud.length}）；橙线：Pareto 前沿（${front.length} 点）；绿圈：加权最优`, 90, 30);
}

function drawCorrelationMatrix() {
  const c = state.lastCorrelation;
  const ctx = els.correlationCanvas.getContext("2d");
  const { width, height } = els.correlationCanvas;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.fillRect(0, 0, width, height);
  if (!c) return;
  const n = c.keys.length;
  const left = 120;
  const top = 110;
  const cell = Math.min((width - left - 10) / n, (height - top - 10) / n);
  ctx.font = "11px Manrope";
  c.labels.forEach((label, i) => {
    ctx.save();
    ctx.translate(left + i * cell + cell / 2 + 4, top - 6);
    ctx.rotate(-Math.PI / 3);
    ctx.fillStyle = "#1f2f29";
    ctx.fillText(label, 0, 0);
    ctx.restore();
    ctx.fillStyle = "#1f2f29";
    ctx.fillText(label, 6, top + i * cell + cell / 2 + 4);
  });
  for (let i = 0; i < n; i += 1) {
    for (let j = 0; j < n; j += 1) {
      const r = c.r[i][j];
      ctx.fillStyle = heatColor(r);
      ctx.fillRect(left + j * cell, top + i * cell, cell - 1, cell - 1);
      if (cell > 26) {
        ctx.fillStyle = Math.abs(r) > 0.5 ? "#fff" : "#1f2f29";
        ctx.font = "9px Manrope";
        ctx.fillText(r.toFixed(2), left + j * cell + 3, top + i * cell + cell / 2 + 3);
      }
    }
  }
  if (c.p) {
    ctx.fillStyle = "#5c695f";
    ctx.font = "11px Manrope";
    ctx.fillText(`Pearson r，n=${c.sampleSize}；颜色深浅表示 |r|，绿正橙负`, left, height - 6);
  }
}

function heatColor(corr) {
  const alpha = Math.min(Math.abs(corr), 1);
  return corr >= 0 ? `rgba(15,106,82,${0.1 + alpha * 0.8})` : `rgba(176,100,44,${0.1 + alpha * 0.8})`;
}

// ---------------------------------------------------------------------------- 6. 工具
function padRange(lo, hi) {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];
  if (hi - lo < 1e-9) return [lo - 1, hi + 1];
  const pad = (hi - lo) * 0.08;
  // 物理量（强度、含量、成本等）不为负：数据全部非负时坐标轴下限不越过 0
  const low = lo >= 0 ? Math.max(0, lo - pad) : lo - pad;
  return [low, hi + pad];
}

function parseCsv(text) {
  const lines = text.replace(/^\ufeff/, "").trim().split(/\r?\n/).filter(Boolean);
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

function mean(values) {
  return values.length ? values.reduce((s, v) => s + v, 0) / values.length : 0;
}

function std(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  return Math.sqrt(values.reduce((s, v) => s + (v - avg) ** 2, 0) / (values.length - 1));
}

function coefficientOfVariation(values) {
  const avg = mean(values);
  return avg === 0 ? 0 : std(values) / avg;
}

function oneWayAnova(groups) {
  const flat = groups.flat();
  const grand = mean(flat);
  const ssBetween = groups.reduce((s, g) => s + g.length * (mean(g) - grand) ** 2, 0);
  const ssWithin = groups.reduce((s, g) => s + g.reduce((inner, v) => inner + (v - mean(g)) ** 2, 0), 0);
  const dfBetween = Math.max(groups.length - 1, 1);
  const dfWithin = Math.max(flat.length - groups.length, 1);
  const f = ssBetween / dfBetween / (ssWithin / dfWithin || 1);
  return { fValue: f, dfBetween, dfWithin, eta2: ssBetween / (ssBetween + ssWithin || 1), effect: ssBetween / (ssBetween + ssWithin || 1), pValue: null, conclusion: "离线模式不计算 p 值。" };
}

function correlation(xs, ys) {
  const n = Math.min(xs.length, ys.length);
  if (!n) return 0;
  const xm = mean(xs);
  const ym = mean(ys);
  let num = 0;
  let vx = 0;
  let vy = 0;
  for (let i = 0; i < n; i += 1) {
    num += (xs[i] - xm) * (ys[i] - ym);
    vx += (xs[i] - xm) ** 2;
    vy += (ys[i] - ym) ** 2;
  }
  return vx && vy ? num / Math.sqrt(vx * vy) : 0;
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
    const k = String(item[key]);
    acc[k] ||= [];
    acc[k].push(item);
    return acc;
  }, {});
}

function downloadCsv(filename, headers, rows) {
  const csv = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");
  const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function seededRandom(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function safeText(error) {
  return error?.message || "操作失败，请稍后重试。";
}

function loadState(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (err) {
    return fallback;
  }
}

function persist(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function labelOf(key) {
  return PARAM_DEFS.find((p) => p.key === key)?.label || METRIC_DEFS.find((m) => m.key === key)?.label || key || "";
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function map(value, fromMin, fromMax, toMin, toMax) {
  if (fromMax === fromMin) return (toMin + toMax) / 2;
  return toMin + ((value - fromMin) / (fromMax - fromMin)) * (toMax - toMin);
}

function formatNumber(value, digits = 2) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return num.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

// p 值专用格式：返回 "=0.0031" 或 "<0.0001"，调用处写作 `p${formatP(v)}`，避免极小值显示为 0
function formatP(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return num < 0.0001 ? "<0.0001" : `=${formatNumber(num, 4)}`;
}

function formatTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("zh-CN", { hour12: false });
}
