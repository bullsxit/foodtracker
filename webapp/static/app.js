const API_BASE = window.API_BASE || "/api";

// ── Telegram WebApp integration ───────────────────────────────────────────────
// Initialise the SDK when running inside Telegram (expand to full height, mark ready)
if (window.Telegram?.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
}

/**
 * Returns the current user's Telegram ID.
 * ① Production: read from Telegram WebApp SDK (automatic, no URL param needed).
 * ② Local dev: fall back to ?tid= query parameter.
 */
function getTelegramId() {
  const sdkUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (sdkUser?.id) return sdkUser.id;

  // Browser preview fallback
  const url = new URL(window.location.href);
  const tid = url.searchParams.get("tid");
  return tid ? parseInt(tid, 10) : null;
}

let telegramId = getTelegramId();
let cachedUser = null;
let _dashboardRetryCount = 0;
const MAX_DASHBOARD_RETRIES = 3;

function showError(message) {
  alert(message);
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Eroare de rețea");
  }
  return response.json();
}

async function fetchJsonForm(path, formData, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Eroare de rețea");
  }
  return response.json();
}

// Tabs – always load fresh data when opening "Apă și progres"
document.querySelectorAll(".tab-button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document
      .querySelectorAll(".tab-button")
      .forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document
      .querySelectorAll(".tab")
      .forEach((s) => s.classList.remove("active"));
    document.getElementById(`tab-${tab}`).classList.add("active");
    if (tab === "progress" && telegramId) {
      loadStats();
    }
    if (tab === "leaderboard") {
      loadLeaderboard();
    }
    if (tab === "history" && telegramId) {
      loadHistory();
    }
  });
});

// Collapsible cards: tap header to expand/collapse form
function initCollapsibles() {
  const pairs = [
    { toggleId: "toggle-manual-meal", bodyId: "body-manual-meal", cardId: "card-manual-meal" },
    { toggleId: "toggle-photo-meal", bodyId: "body-photo-meal", cardId: "card-photo-meal" },
    { toggleId: "toggle-water", bodyId: "body-water", cardId: "card-water" },
    { toggleId: "toggle-workout", bodyId: "body-workout", cardId: "card-workout" },
  ];
  pairs.forEach(({ toggleId, bodyId, cardId }) => {
    const toggle = document.getElementById(toggleId);
    const body = document.getElementById(bodyId);
    const card = document.getElementById(cardId);
    if (!toggle || !body || !card) return;
    toggle.addEventListener("click", () => {
      const isOpen = !body.hidden;
      body.hidden = isOpen;
      toggle.setAttribute("aria-expanded", isOpen ? "false" : "true");
      card.classList.toggle("is-open", !isOpen);
    });
  });
}
initCollapsibles();

// Toggle weight chart visibility
const toggleWeightChartBtn = document.getElementById("toggle-weight-chart");
const weightChartContainer = document.getElementById("weight-chart-container");
if (toggleWeightChartBtn && weightChartContainer) {
  toggleWeightChartBtn.addEventListener("click", () => {
    const isHidden = weightChartContainer.style.display === "none" || !weightChartContainer.style.display;
    if (isHidden) {
      weightChartContainer.style.display = "block";
      if (telegramId && !weightChartContainer.querySelector("img")) {
        const chartUrl = `${API_BASE}/chart/weight/${telegramId}?t=${Date.now()}`;
        weightChartContainer.innerHTML = `<img src="${chartUrl}" alt="Grafic greutate" />`;
      }
      toggleWeightChartBtn.textContent = "Ascunde grafic greutate";
    } else {
      weightChartContainer.style.display = "none";
      toggleWeightChartBtn.textContent = "Arată grafic greutate (30 zile)";
    }
  });
}

// Toggle calories chart visibility
const toggleCaloriesChartBtn = document.getElementById("toggle-calories-chart");
const caloriesChartContainer = document.getElementById("calories-chart-container");
if (toggleCaloriesChartBtn && caloriesChartContainer) {
  toggleCaloriesChartBtn.addEventListener("click", () => {
    const isHidden = caloriesChartContainer.style.display === "none" || !caloriesChartContainer.style.display;
    if (isHidden) {
      caloriesChartContainer.style.display = "block";
      if (telegramId && !caloriesChartContainer.querySelector("img")) {
        const chartUrl = `${API_BASE}/chart/calories/${telegramId}?t=${Date.now()}`;
        caloriesChartContainer.innerHTML = `<img src="${chartUrl}" alt="Grafic calorii" />`;
      }
      toggleCaloriesChartBtn.textContent = "Ascunde grafic calorii";
    } else {
      caloriesChartContainer.style.display = "none";
      toggleCaloriesChartBtn.textContent = "Arată grafic calorii (30 zile)";
    }
  });
}

async function loadDashboard() {
  telegramId = getTelegramId();
  const onboardingCard = document.getElementById("onboarding-card");
  const dashboardContent = document.getElementById("dashboard-content");
  const onboardingHint = document.getElementById("onboarding-no-id-hint");

  if (!telegramId) {
    if (onboardingHint) onboardingHint.style.display = "block";
    if (onboardingCard) onboardingCard.style.display = "block";
    if (dashboardContent) dashboardContent.style.display = "none";
    const greetingBanner = document.getElementById("greeting-banner");
    if (greetingBanner) greetingBanner.style.display = "none";
    if (_dashboardRetryCount < MAX_DASHBOARD_RETRIES) {
      _dashboardRetryCount += 1;
      setTimeout(loadDashboard, 400 * _dashboardRetryCount);
    }
    return;
  }

  if (onboardingHint) onboardingHint.style.display = "none";
  _dashboardRetryCount = 0;

  try {
    const response = await fetch(`${API_BASE}/dashboard/${telegramId}`, {
      headers: { "Content-Type": "application/json" },
    });

    if (response.status === 404) {
      cachedUser = null;
      const greetingBanner = document.getElementById("greeting-banner");
      if (greetingBanner) greetingBanner.style.display = "none";
      if (onboardingHint) onboardingHint.style.display = "none";
      if (onboardingCard) onboardingCard.style.display = "block";
      if (dashboardContent) dashboardContent.style.display = "none";
      syncSettingsFromUser();
      await loadStats();
      return;
    }

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Eroare de rețea");
    }

    const data = await response.json();
    const user = data.user;
    cachedUser = user;

    if (onboardingCard) onboardingCard.style.display = "none";
    if (dashboardContent) dashboardContent.style.display = "block";
    const greetingBanner = document.getElementById("greeting-banner");
    if (greetingBanner) greetingBanner.style.display = "block";

    const profileEl = document.getElementById("profile-summary");
    const greetingMap = {
      "Slăbire":   { text: "Hai să slăbim! 🔥",          sub: "Ești pe drumul cel bun." },
      "Menținere": { text: "Hai să ne menținem! ⚖️",      sub: "Consistența e cheia succesului." },
      "Creștere":  { text: "Hai să ne dezvoltăm! 💪",     sub: "Fiecare zi contează." },
    };
    const g = greetingMap[user.goal] || { text: "Bun venit! 👋", sub: "" };
    profileEl.innerHTML = `
      <div class="greeting-hello">Salut, ${user.name}!</div>
      <div class="greeting-goal">${g.text}</div>
      <div class="greeting-sub">${g.sub}</div>
      <div class="greeting-meta">
        <span>${user.current_weight.toFixed(1)} kg</span>
        <span>·</span>
        <span>${Math.round(user.target_calories || 2000)} kcal / zi</span>
      </div>
    `;

    const calEl = document.getElementById("calories-today");
    const consumed = data.calories_today || 0;
    const target = Math.max(1, user.target_calories || 2000);
    const remaining = Math.max(0, target - consumed);
    const pct = Math.min(100, (consumed / target) * 100);
    const consumedProtein = data.consumed_protein ?? 0;
    const consumedCarbs = data.consumed_carbs ?? 0;
    const consumedFat = data.consumed_fat ?? 0;
    const targetP = data.target_protein_g ?? (target * 0.3 / 4);
    const targetC = data.target_carbs_g ?? (target * 0.4 / 4);
    const targetF = data.target_fat_g ?? (target * 0.3 / 9);
    const remP = Math.max(0, targetP - consumedProtein);
    const remC = Math.max(0, targetC - consumedCarbs);
    const remF = Math.max(0, targetF - consumedFat);
    const pctP = Math.min(100, (consumedProtein / (targetP || 1)) * 100);
    const pctC = Math.min(100, (consumedCarbs / (targetC || 1)) * 100);
    const pctF = Math.min(100, (consumedFat / (targetF || 1)) * 100);
    calEl.innerHTML = `
      <div class="calories-line">${consumed.toFixed(0)} / ${target.toFixed(0)} kcal</div>
      <div class="progress-track"><div class="progress-fill" style="width: ${pct}%;"></div></div>
      <div class="calories-remaining">${remaining.toFixed(0)} kcal rămase azi</div>
      <div class="macro-row"><span class="label">Proteine</span><span class="value">${consumedProtein.toFixed(0)} / ${targetP.toFixed(0)} g</span><span class="remaining">${remP.toFixed(0)} g rămase</span></div>
      <div class="progress-track"><div class="progress-fill" style="width: ${pctP}%;"></div></div>
      <div class="macro-row"><span class="label">Carbohidrați</span><span class="value">${consumedCarbs.toFixed(0)} / ${targetC.toFixed(0)} g</span><span class="remaining">${remC.toFixed(0)} g rămase</span></div>
      <div class="progress-track"><div class="progress-fill" style="width: ${pctC}%;"></div></div>
      <div class="macro-row"><span class="label">Grăsimi</span><span class="value">${consumedFat.toFixed(0)} / ${targetF.toFixed(0)} g</span><span class="remaining">${remF.toFixed(0)} g rămase</span></div>
      <div class="progress-track"><div class="progress-fill" style="width: ${pctF}%;"></div></div>
    `;

    if (data.weight_logged_today === false) {
      const weightOverlay = document.getElementById("daily-weight-overlay");
      if (weightOverlay) weightOverlay.style.display = "flex";
    } else {
      const weightOverlay = document.getElementById("daily-weight-overlay");
      if (weightOverlay) weightOverlay.style.display = "none";
    }

    const waterEl = document.getElementById("water-today");
    const water = data.water_today_ml || 0;
    waterEl.innerHTML = `
      <div class="metric">
        <div class="metric-label">Apă băută azi</div>
        <div class="metric-value accent">${water.toFixed(0)} ml</div>
      </div>
      <div class="muted">Țintă recomandată: ~2000 ml / zi</div>
    `;
  } catch (e) {
    console.error(e);
    cachedUser = null;
    if (onboardingHint) onboardingHint.style.display = "none";
    if (onboardingCard) onboardingCard.style.display = "block";
    if (dashboardContent) dashboardContent.style.display = "none";
    const greetingBanner = document.getElementById("greeting-banner");
    if (greetingBanner) greetingBanner.style.display = "none";
    const errEl = document.getElementById("onboarding-error");
    if (errEl) {
      errEl.textContent = "Completează formularul de mai jos pentru a crea profilul.";
      errEl.style.display = "block";
    }
  }
  syncSettingsFromUser();
}

// Onboarding form: create profile when none exists
const onboardingSubmit = document.getElementById("onboarding-submit");
if (onboardingSubmit) {
  onboardingSubmit.addEventListener("click", async () => {
    const currentId = getTelegramId();
    if (!currentId) {
      const errEl = document.getElementById("onboarding-error");
      if (errEl) {
        errEl.textContent = "Nu te putem identifica. Deschide aplicația din butonul Menu al botului și încearcă din nou.";
        errEl.style.display = "block";
      }
      return;
    }
    telegramId = currentId;
    const errEl = document.getElementById("onboarding-error");
    const nameEl = document.getElementById("onboarding-name");
    const ageEl = document.getElementById("onboarding-age");
    const heightEl = document.getElementById("onboarding-height");
    const weightEl = document.getElementById("onboarding-weight");
    const genderEl = document.getElementById("onboarding-gender");
    const goalEl = document.getElementById("onboarding-goal");
    const activityEl = document.getElementById("onboarding-activity");
    const name = nameEl && nameEl.value ? nameEl.value.trim() : "";
    const age = ageEl && ageEl.value ? ageEl.value : "";
    const height = heightEl && heightEl.value ? heightEl.value : "";
    const weight = weightEl && weightEl.value ? weightEl.value : "";
    const gender = genderEl ? genderEl.value : "male";
    const goal = goalEl ? goalEl.value : "Menținere";
    const activity = activityEl ? activityEl.value : "Sedentar";

    if (!name || !age || !height || !weight) {
      if (errEl) {
        errEl.textContent = "Completează toate câmpurile obligatorii.";
        errEl.style.display = "block";
      }
      return;
    }
    if (errEl) errEl.style.display = "none";

    const fd = new FormData();
    fd.append("telegram_id", String(telegramId));
    fd.append("name", name);
    fd.append("age", age);
    fd.append("height_cm", height);
    fd.append("weight_kg", weight);
    fd.append("gender", gender);
    fd.append("goal", goal);
    fd.append("activity_level", activity);

    try {
      await fetchJsonForm("/register", fd);
      await loadDashboard();
    } catch (e) {
      console.error(e);
      if (errEl) {
        let msg = e.message || "Nu am putut crea profilul.";
        try {
          const parsed = JSON.parse(e.message || "{}");
          if (parsed.detail) msg = typeof parsed.detail === "string" ? parsed.detail : msg;
        } catch (_) {}
        errEl.textContent = msg;
        errEl.style.display = "block";
      }
    }
  });
}

function syncSettingsFromUser() {
  if (!cachedUser) return;
  const ageEl = document.getElementById("settings-age");
  const heightEl = document.getElementById("settings-height");
  const goalEl = document.getElementById("settings-goal");
  const actEl = document.getElementById("settings-activity");
  const weightInput = document.getElementById("weight-input");
  if (ageEl) ageEl.value = cachedUser.age ?? "";
  if (heightEl) heightEl.value = cachedUser.height_cm ?? "";
  if (goalEl) goalEl.value = cachedUser.goal ?? "Slăbire";
  if (actEl) actEl.value = cachedUser.activity_level ?? "Sedentar";
  if (weightInput && cachedUser.current_weight != null) {
    weightInput.value = cachedUser.current_weight.toFixed(1);
  }
}

// Water buttons
document.querySelectorAll("[data-add-water]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const amount = parseInt(btn.dataset.addWater, 10);
    try {
      const data = await fetchJson(`/water/${telegramId}/add?amount_ml=${amount}`, {
        method: "POST",
      });
      const waterEl = document.getElementById("water-today");
      const water = data.water_today_ml || 0;
      waterEl.innerHTML = `
        <div class="metric">
          <div class="metric-label">Apă băută azi</div>
          <div class="metric-value accent">${water.toFixed(0)} ml</div>
        </div>
        <div class="muted">Țintă recomandată: ~2000 ml / zi</div>
      `;
    } catch (e) {
      console.error(e);
      showError("Nu am putut actualiza apa de azi.");
    }
  });
});

// History – legacy date-picker flow (only if present in DOM)
const loadHistoryBtn = document.getElementById("load-history");
const historyDateInput = document.getElementById("history-date");
if (loadHistoryBtn && historyDateInput) {
  loadHistoryBtn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const dateInput = document.getElementById("history-date");
    if (!dateInput.value) {
      showError("Te rog alege o dată.");
      return;
    }
    const container = document.getElementById("history-content");
    if (container) {
      container.innerHTML = "Se încarcă...";
      try {
        const data = await fetchJson(
          `/meals/${telegramId}/${encodeURIComponent(dateInput.value)}`
        );
        if (!data.items.length) {
          container.innerHTML = `<p class="muted">Nu există înregistrări pentru această zi.</p>`;
          return;
        }
        const itemsHtml = data.items
          .map(
            (item) => `
        <div class="history-item">
          <div><span class="accent">${item.meal_type || "Masă"}</span> – ${
              item.name
            }</div>
          <div class="muted">
            ${item.calories.toFixed(0)} kcal
            ${
              item.protein != null
                ? ` • Prot: ${item.protein.toFixed(1)} g`
                : ""
            }
            ${
              item.carbs != null ? ` • Carb: ${item.carbs.toFixed(1)} g` : ""
            }
            ${item.fat != null ? ` • Grăsimi: ${item.fat.toFixed(1)} g` : ""}
          </div>
        </div>
      `
          )
          .join("");
        container.innerHTML = `
        <p class="muted">Total: ${data.total_calories.toFixed(0)} kcal</p>
        ${itemsHtml}
      `;
      } catch (e) {
        console.error(e);
        container.innerHTML = "";
        showError("Nu am putut încărca istoricul pentru ziua selectată.");
      }
    }
  });
}

async function loadStats() {
  if (!telegramId) {
    return;
  }
  try {
    const data = await fetchJson(`/stats/${telegramId}`);

    // Weight summary
    const weightSummaryEl = document.getElementById("weight-summary");
    const weights = data.weights_30_days || [];
    if (weights.length > 0) {
      const start = weights[0].weight;
      const current = weights[weights.length - 1].weight;
      const diff = current - start;
      weightSummaryEl.innerHTML = `
        <div class="metric">
          <div class="metric-label">Greutate început perioadă</div>
          <div class="metric-value">${start.toFixed(1)} kg</div>
        </div>
        <div class="metric">
          <div class="metric-label">Greutate curentă</div>
          <div class="metric-value accent">${current.toFixed(1)} kg</div>
        </div>
      `;
    } else {
      weightSummaryEl.innerHTML =
        '<p class="muted">Nu există încă măsurători de greutate în ultimele 30 de zile.</p>';
    }

    // Weight progress "shower" – kg lost/gained in last 30 days
    const showerEl = document.getElementById("weight-progress-shower");
    if (showerEl && weights.length >= 2) {
      const startW = weights[0].weight;
      const currentW = weights[weights.length - 1].weight;
      const diffW = currentW - startW;
      const sign = diffW >= 0 ? "+" : "";
      const pct = startW > 0 ? Math.min(100, Math.abs(diffW) / startW * 100) : 0;
      showerEl.innerHTML = `
        <div class="shower-label">În ultimele 30 zile</div>
        <div class="shower-value">${sign}${diffW.toFixed(1)} kg</div>
        <div class="progress-track"><div class="progress-fill" style="width: ${pct}%;"></div></div>
      `;
      showerEl.style.display = "block";
    } else if (showerEl) {
      showerEl.innerHTML = '<div class="shower-label">Adaugă măsurători de greutate pentru a vedea progresul.</div>';
      showerEl.style.display = "block";
    }

    // Calories chart (30 days) – loaded lazily on button click, reset here so
    // a fresh image is fetched next time the user opens the chart.
    if (caloriesChartContainer) {
      caloriesChartContainer.innerHTML = "";
      caloriesChartContainer.style.display = "none";
    }
    if (toggleCaloriesChartBtn) {
      toggleCaloriesChartBtn.textContent = "Arată grafic calorii (30 zile)";
    }

    const summaryEl = document.getElementById("stats-summary");
    const avg = data.average_calories_7_days;
    const avgSafe = avg != null && avg <= 15000 ? avg.toFixed(0) : "–";
    summaryEl.innerHTML = `
      <div class="metric">
        <div class="metric-label">Media caloriilor (7 zile)</div>
        <div class="metric-value accent">${avgSafe} kcal</div>
      </div>
      <div class="metric">
        <div class="metric-label">Puncte de date calorii (30 zile)</div>
        <div class="metric-value">${data.calories_30_days.length || 0}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Măsurători greutate (30 zile)</div>
        <div class="metric-value">${data.weights_30_days.length || 0}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Înregistrări apă (30 zile)</div>
        <div class="metric-value">${data.water_30_days.length || 0}</div>
      </div>
    `;

    // Suggestions
    const suggestionsEl = document.getElementById("suggestions-list");
    if (suggestionsEl && data.suggestions && data.suggestions.length > 0) {
      suggestionsEl.innerHTML = `<ul class="suggestions-list">${data.suggestions
        .map((s) => `<li>${s}</li>`)
        .join("")}</ul>`;
    } else if (suggestionsEl) {
      suggestionsEl.innerHTML = '<p class="muted">Completează mesele pentru sugestii personalizate.</p>';
    }
  } catch (e) {
    console.error(e);
  }
}

// Initial load – delay slightly so Telegram WebApp can inject user id
window.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("history-date");
  if (dateInput) {
    const today = new Date().toISOString().slice(0, 10);
    dateInput.value = today;
  }
  const reloadSessionBtn = document.getElementById("reload-session-btn");
  if (reloadSessionBtn) {
    reloadSessionBtn.addEventListener("click", () => {
      cachedUser = null;
      _dashboardRetryCount = 0;
      location.reload();
    });
  }
  setTimeout(() => {
    loadDashboard();
    loadStats();
    if (getTelegramId()) {
      loadScore();
      loadWeekWorkouts();
    }
  }, 150);
});

// Manual meal saving
const saveManualBtn = document.getElementById("save-manual-meal");
if (saveManualBtn) {
  saveManualBtn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const typeEl = document.getElementById("manual-meal-type");
    const nameEl = document.getElementById("manual-meal-name");
    const gramsEl = document.getElementById("manual-meal-grams");
    const calEl = document.getElementById("manual-meal-calories");
    const protEl = document.getElementById("manual-meal-protein");
    const carbsEl = document.getElementById("manual-meal-carbs");
    const fatEl = document.getElementById("manual-meal-fat");

    if (!nameEl.value.trim()) {
      showError("Te rog introdu numele mâncării.");
      return;
    }
    if (!calEl.value) {
      showError("Te rog introdu caloriile.");
      return;
    }

    let name = nameEl.value.trim();
    if (gramsEl.value) {
      name = `${name} (${gramsEl.value} g)`;
    }

    const fd = new FormData();
    fd.append("name", name);
    fd.append("calories", calEl.value);
    if (protEl.value) fd.append("protein", protEl.value);
    if (carbsEl.value) fd.append("carbs", carbsEl.value);
    if (fatEl.value) fd.append("fat", fatEl.value);
    fd.append("meal_type", typeEl.value);

    try {
      await fetchJsonForm(`/meals/${telegramId}/add_manual`, fd);
      showError("Masa a fost salvată.");
      // Reset form and refresh dashboard + score
      nameEl.value = "";
      gramsEl.value = "";
      calEl.value = "";
      protEl.value = "";
      carbsEl.value = "";
      fatEl.value = "";
      await loadDashboard();
      if (telegramId) await loadScore();
    } catch (e) {
      console.error(e);
      showError("Nu am putut salva masa.");
    }
  });
}

// Photo AI analysis
const photoAnalyzeBtn = document.getElementById("photo-analyze");
if (photoAnalyzeBtn) {
  photoAnalyzeBtn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const fileInput = document.getElementById("photo-meal-file");
    const typeEl = document.getElementById("photo-meal-type");
    const resultEl = document.getElementById("photo-analysis-result");
    if (!fileInput.files || !fileInput.files[0]) {
      showError("Te rog selectează o fotografie cu mâncarea.");
      return;
    }
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    fd.append("meal_type", typeEl.value);
    resultEl.textContent = "Analizez fotografia...";
    try {
      const data = await fetchJsonForm(
        `/meals/${telegramId}/analyze_image`,
        fd
      );
      const a = data.analysis;
      // Precompletăm formularul manual cu valorile detectate
      const nameEl = document.getElementById("manual-meal-name");
      const calEl = document.getElementById("manual-meal-calories");
      const protEl = document.getElementById("manual-meal-protein");
      const carbsEl = document.getElementById("manual-meal-carbs");
      const fatEl = document.getElementById("manual-meal-fat");
      const manualTypeEl = document.getElementById("manual-meal-type");
      if (nameEl && a.name) nameEl.value = a.name;
      if (calEl && a.calories != null) calEl.value = a.calories;
      if (protEl && a.protein != null) protEl.value = a.protein;
      if (carbsEl && a.carbs != null) carbsEl.value = a.carbs;
      if (fatEl && a.fat != null) fatEl.value = a.fat;
      if (manualTypeEl && a.meal_type) manualTypeEl.value = a.meal_type;

      resultEl.textContent =
        "Am detectat o masă pe care am completat-o automat în formularul de mai sus. Verifică valorile și apasă „Salvează masa”.";
    } catch (e) {
      console.error(e);
      resultEl.textContent = "";
      showError("Nu am putut analiza fotografia.");
    }
  });
}

// Save weight
const saveWeightBtn = document.getElementById("save-weight");
if (saveWeightBtn) {
  saveWeightBtn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const weightEl = document.getElementById("weight-input");
    if (!weightEl.value) {
      showError("Te rog introdu greutatea curentă.");
      return;
    }
    const fd = new FormData();
    fd.append("weight", weightEl.value);
    try {
      const data = await fetchJsonForm(
        `/user/${telegramId}/log_weight`,
        fd
      );
      cachedUser = data.user;
      syncSettingsFromUser();
      await loadDashboard();
      await loadStats();
      showError("Greutatea a fost salvată.");
    } catch (e) {
      console.error(e);
      showError("Nu am putut salva greutatea.");
    }
  });
}

// Settings: personal data
const savePersonalBtn = document.getElementById("save-personal");
if (savePersonalBtn) {
  savePersonalBtn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const ageEl = document.getElementById("settings-age");
    const heightEl = document.getElementById("settings-height");
    if (!ageEl.value || !heightEl.value) {
      showError("Te rog introdu vârsta și înălțimea.");
      return;
    }
    const fd = new FormData();
    fd.append("age", ageEl.value);
    fd.append("height_cm", heightEl.value);
    try {
      const data = await fetchJsonForm(
        `/user/${telegramId}/update_personal`,
        fd
      );
      cachedUser = data.user;
      syncSettingsFromUser();
      await loadDashboard();
      showError("Datele personale au fost actualizate.");
    } catch (e) {
      console.error(e);
      showError("Nu am putut actualiza datele personale.");
    }
  });
}

// Settings: goal & activity
const saveGoalActivityBtn = document.getElementById("save-goal-activity");
if (saveGoalActivityBtn) {
  saveGoalActivityBtn.addEventListener("click", async () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    const goalEl = document.getElementById("settings-goal");
    const actEl = document.getElementById("settings-activity");
    const goalFd = new FormData();
    goalFd.append("goal", goalEl.value);
    try {
      const goalData = await fetchJsonForm(
        `/user/${telegramId}/update_goal`,
        goalFd
      );
      cachedUser = goalData.user;
    } catch (e) {
      console.error(e);
      showError("Nu am putut actualiza obiectivul.");
      return;
    }

    const actFd = new FormData();
    actFd.append("activity_level", actEl.value);
    try {
      const actData = await fetchJsonForm(
        `/user/${telegramId}/update_activity`,
        actFd
      );
      cachedUser = actData.user;
      syncSettingsFromUser();
      await loadDashboard();
      showError("Obiectivul și activitatea au fost actualizate.");
    } catch (e) {
      console.error(e);
      showError("Nu am putut actualiza nivelul de activitate.");
    }
  });
}

// Reset profile: custom confirm dialog
const resetProfileBtn = document.getElementById("reset-profile");
const confirmOverlay = document.getElementById("confirm-reset-overlay");
const confirmResetNo = document.getElementById("confirm-reset-no");
const confirmResetYes = document.getElementById("confirm-reset-yes");

if (resetProfileBtn) {
  resetProfileBtn.addEventListener("click", () => {
    if (!telegramId) {
      showError("Nu pot identifica utilizatorul.");
      return;
    }
    if (confirmOverlay) confirmOverlay.style.display = "flex";
  });
}

if (confirmResetNo) {
  confirmResetNo.addEventListener("click", () => {
    if (confirmOverlay) confirmOverlay.style.display = "none";
  });
}

if (confirmResetYes) {
  confirmResetYes.addEventListener("click", async () => {
    if (!telegramId) return;
    if (confirmOverlay) confirmOverlay.style.display = "none";
    try {
      const response = await fetch(`${API_BASE}/user/${telegramId}/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Eroare server");
      }
      cachedUser = null;
      showError("Profilul a fost șters.");
      await loadDashboard();
    } catch (e) {
      console.error(e);
      showError("Nu am putut șterge profilul.");
    }
  });
}

// Daily weight popup – save and close only after saving
const dailyWeightOverlay = document.getElementById("daily-weight-overlay");
const dailyWeightInput = document.getElementById("daily-weight-input");
const dailyWeightSave = document.getElementById("daily-weight-save");
if (dailyWeightSave && dailyWeightInput) {
  dailyWeightSave.addEventListener("click", async () => {
    if (!telegramId) return;
    const val = dailyWeightInput.value.trim();
    if (!val) {
      showError("Introdu greutatea în kg.");
      return;
    }
    const num = parseFloat(val.replace(",", "."));
    if (isNaN(num) || num < 1 || num > 400) {
      showError("Greutate invalidă (1–400 kg).");
      return;
    }
    try {
      const fd = new FormData();
      fd.append("weight", String(num));
      await fetchJsonForm(`/user/${telegramId}/log_weight`, fd);
      dailyWeightInput.value = "";
      if (dailyWeightOverlay) dailyWeightOverlay.style.display = "none";
      await loadDashboard();
    } catch (e) {
      console.error(e);
      showError("Nu am putut salva greutatea.");
    }
  });
}


// ── Score & Streak ────────────────────────────────────────────────────────────

async function loadScore() {
  if (!telegramId) return;
  const scoreEl = document.getElementById("score-value");
  const streakEl = document.getElementById("streak-value");
  try {
    const data = await fetchJson(`/score/${telegramId}`);
    const score = data.score ?? 0;
    const streak = data.streak ?? 0;
    let scoreClass = "score-low";
    if (score >= 85) scoreClass = "score-top";
    else if (score >= 70) scoreClass = "score-high";
    else if (score >= 50) scoreClass = "score-mid";
    if (scoreEl) {
      scoreEl.textContent = score;
      scoreEl.className = `score-number ${scoreClass}`;
    }
    if (streakEl) {
      streakEl.textContent = streak > 0
        ? `🔥 ${streak} ${streak === 1 ? "zi" : "zile"}`
        : "— nicio zi consecutivă";
    }
  } catch (e) {
    console.error("loadScore:", e);
  }
}

// ── Workouts ──────────────────────────────────────────────────────────────────

async function loadWeekWorkouts() {
  if (!telegramId) return;
  const summaryEl = document.getElementById("workout-week-summary");
  try {
    const data = await fetchJson(`/workout/${telegramId}/week`);
    if (!summaryEl) return;
    if (data.count === 0) {
      summaryEl.innerHTML = `<span class="workout-none">Niciun antrenament săptămâna asta</span>`;
    } else {
      const miniItems = data.items.slice(0, 3)
        .map(w => `<div class="workout-item-mini">${w.name}${w.duration_min ? ` · ${w.duration_min} min` : ""}</div>`)
        .join("");
      const more = data.items.length > 3
        ? `<div class="workout-item-mini muted">+${data.items.length - 3} mai multe</div>` : "";
      summaryEl.innerHTML = `
        <div class="workout-count">${data.count} antrenament${data.count !== 1 ? "e" : ""}</div>
        <div class="workout-burned">${data.total_calories_burned.toFixed(0)} kcal arse</div>
        <div class="workout-list">${miniItems}${more}</div>`;
    }
  } catch (e) {
    console.error("loadWeekWorkouts:", e);
  }
}

const saveWorkoutBtn = document.getElementById("save-workout");
if (saveWorkoutBtn) {
  saveWorkoutBtn.addEventListener("click", async () => {
    if (!telegramId) { showError("Nu pot identifica utilizatorul."); return; }
    const nameEl = document.getElementById("workout-name");
    const calEl  = document.getElementById("workout-calories");
    const durEl  = document.getElementById("workout-duration");
    if (!nameEl.value.trim()) { showError("Te rog introdu tipul antrenamentului."); return; }
    if (!calEl.value || Number(calEl.value) < 0) { showError("Te rog introdu caloriile arse (≥ 0)."); return; }
    const fd = new FormData();
    fd.append("name", nameEl.value.trim());
    fd.append("calories_burned", calEl.value);
    if (durEl.value) fd.append("duration_min", durEl.value);
    try {
      await fetchJsonForm(`/workout/${telegramId}/add`, fd);
      nameEl.value = ""; calEl.value = ""; durEl.value = "";
      await Promise.all([loadWeekWorkouts(), loadScore()]);
      showError("Antrenament salvat! 💪");
    } catch (e) {
      console.error(e);
      showError("Nu am putut salva antrenamentul.");
    }
  });
}

// ── Leaderboard ───────────────────────────────────────────────────────────────

async function loadLeaderboard() {
  const container = document.getElementById("leaderboard-content");
  if (!container) return;
  container.innerHTML = `<p class="muted">Se încarcă…</p>`;
  try {
    const data = await fetchJson("/leaderboard");
    const list = data.leaderboard || [];
    if (list.length === 0) {
      container.innerHTML = `<p class="muted">Niciun utilizator înregistrat încă.</p>`;
      return;
    }
    const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };
    const rows = list.map((entry) => {
      const medal = medalMap[entry.rank] || `#${entry.rank}`;
      const isMe  = Number(entry.telegram_id) === Number(telegramId);
      const scoreCls = entry.score >= 85 ? "score-top"
                     : entry.score >= 70 ? "score-high"
                     : entry.score >= 50 ? "score-mid" : "score-low";
      return `
        <div class="lb-row${isMe ? " lb-me" : ""}">
          <div class="lb-rank">${medal}</div>
          <div class="lb-info">
            <div class="lb-name">${entry.name}${isMe ? " <span class='lb-you'>(tu)</span>" : ""}</div>
            <div class="lb-goal muted">${entry.goal}</div>
          </div>
          <div class="lb-stats">
            <div class="lb-score ${scoreCls}">${entry.score}<span class="lb-max">/100</span></div>
            <div class="lb-streak">${entry.streak > 0 ? `🔥 ${entry.streak}z` : "—"}</div>
          </div>
        </div>`;
    }).join("");
    container.innerHTML = `<div class="lb-list">${rows}</div>`;
  } catch (e) {
    console.error("loadLeaderboard:", e);
    container.innerHTML = `<p class="muted">Nu am putut încărca clasamentul.</p>`;
  }
}

// ── History – 7-day accordion ─────────────────────────────────────────────────

function _dayLabel(dateStr) {
  const d = new Date(dateStr + "T12:00:00");
  const today = new Date();
  today.setHours(12,0,0,0);
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Azi";
  if (d.toDateString() === yesterday.toDateString()) return "Ieri";
  return d.toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "short" });
}

function _buildDayDetail(d) {
  // Meals grouped
  let mealsHtml = "";
  if (d.meal_groups && d.meal_groups.length) {
    for (const g of d.meal_groups) {
      const rows = g.items.map(item => `
        <div class="hist-food-row">
          <span class="hist-food-name">${item.name}</span>
          <span class="hist-food-cal">${item.calories.toFixed(0)} kcal</span>
        </div>
        ${item.protein != null || item.carbs != null || item.fat != null ? `
        <div class="hist-food-macros">
          ${item.protein != null ? `P: ${item.protein.toFixed(0)}g` : ""}
          ${item.carbs  != null ? ` · C: ${item.carbs.toFixed(0)}g` : ""}
          ${item.fat    != null ? ` · G: ${item.fat.toFixed(0)}g`   : ""}
        </div>` : ""}
      `).join("");
      mealsHtml += `<div class="hist-meal-group">
        <div class="hist-meal-type">${g.meal_type}</div>
        ${rows}
      </div>`;
    }
  } else {
    mealsHtml = `<p class="muted" style="margin:6px 0 10px;">Nicio masă înregistrată.</p>`;
  }

  // Workouts
  let workoutsHtml = "";
  if (d.workouts && d.workouts.length) {
    workoutsHtml = `<div class="hist-section-title">Antrenamente</div>` +
      d.workouts.map(w => `
        <div class="hist-food-row">
          <span class="hist-food-name">${w.name}${w.duration_min ? ` (${w.duration_min} min)` : ""}</span>
          <span class="hist-food-cal" style="color:#0ea5e9;">-${w.calories_burned.toFixed(0)} kcal</span>
        </div>`
      ).join("");
  }

  return `
    <div class="hist-macros-row">
      <div class="hist-macro-pill"><span>🔥</span><b>${d.total_calories.toFixed(0)}</b><span>kcal</span></div>
      <div class="hist-macro-pill"><span>💧</span><b>${d.water_ml.toFixed(0)}</b><span>ml</span></div>
      ${d.weight_kg != null ? `<div class="hist-macro-pill"><span>⚖️</span><b>${d.weight_kg.toFixed(1)}</b><span>kg</span></div>` : ""}
    </div>
    <div class="hist-macro-detail muted">
      Prot: ${d.total_protein.toFixed(0)}g · Carb: ${d.total_carbs.toFixed(0)}g · Grăsimi: ${d.total_fat.toFixed(0)}g
    </div>
    <div class="hist-divider"></div>
    ${mealsHtml}
    ${workoutsHtml}
  `;
}

async function loadHistory() {
  if (!telegramId) return;
  const container = document.getElementById("history-days");
  if (!container) return;
  container.innerHTML = `<p class="muted">Se încarcă…</p>`;

  // Build last 7 dates (today first)
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(); d.setDate(d.getDate() - i);
    dates.push(d.toISOString().slice(0, 10));
  }

  // Fetch all 7 days in parallel
  const results = await Promise.all(
    dates.map(d => fetchJson(`/day/${telegramId}/${d}`).catch(() => null))
  );

  container.innerHTML = "";

  results.forEach((data, idx) => {
    const dateStr = dates[idx];
    const label = _dayLabel(dateStr);
    const hasData = data && (data.total_calories > 0 || data.water_ml > 0 || data.workouts?.length > 0);
    const calText = data && data.total_calories > 0 ? `${data.total_calories.toFixed(0)} kcal` : "–";

    const row = document.createElement("div");
    row.className = "hist-day-row";
    row.dataset.open = "0";

    row.innerHTML = `
      <div class="hist-day-header">
        <div class="hist-day-info">
          <span class="hist-day-label">${label}</span>
          <span class="hist-day-date muted">${dateStr}</span>
        </div>
        <div class="hist-day-right">
          <span class="hist-cal-badge${hasData ? " has-data" : ""}">${calText}</span>
          <span class="hist-chevron">›</span>
        </div>
      </div>
      <div class="hist-day-body" style="display:none;">
        ${data ? _buildDayDetail(data) : `<p class="muted" style="padding:8px 0;">Nicio dată disponibilă.</p>`}
      </div>
    `;

    row.querySelector(".hist-day-header").addEventListener("click", () => {
      const body = row.querySelector(".hist-day-body");
      const chevron = row.querySelector(".hist-chevron");
      const isOpen = row.dataset.open === "1";
      if (isOpen) {
        body.style.display = "none";
        chevron.style.transform = "";
        row.dataset.open = "0";
      } else {
        body.style.display = "block";
        chevron.style.transform = "rotate(90deg)";
        row.dataset.open = "1";
      }
    });

    container.appendChild(row);
  });
}
