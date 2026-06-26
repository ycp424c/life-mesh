(function () {
  const state = window.LIFEMESH_PROJECT_STATE;

  const byId = (id) => document.getElementById(id);
  const esc = (value) =>
    String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    })[char]);

  function toneClass(tone) {
    return `tone-${String(tone || "neutral").toLowerCase()}`;
  }

  function renderOverview() {
    byId("project-state").textContent = state.state;
    byId("project-summary").textContent = state.summary;
    byId("overall-progress").style.width = `${state.overallProgress}%`;
    byId("current-phase").textContent = state.currentPhase;
    byId("last-updated").textContent = `更新 ${state.lastUpdated}`;

    byId("metric-grid").innerHTML = state.metrics.map((metric) => `
      <article class="metric ${toneClass(metric.tone)}">
        <span>${esc(metric.label)}</span>
        <strong>${esc(metric.value)}</strong>
        <small>${esc(metric.detail)}</small>
      </article>
    `).join("");
  }

  function renderWork() {
    byId("work-lanes").innerHTML = state.work.map((lane) => `
      <article class="lane">
        <h3>${esc(lane.lane)}</h3>
        <ul>
          ${lane.items.map((item) => `<li>${esc(item)}</li>`).join("")}
        </ul>
      </article>
    `).join("");
  }

  function renderPhases() {
    byId("phase-track").innerHTML = state.phases.map((phase) => `
      <article class="phase ${toneClass(phase.status)}">
        <div class="phase-top">
          <span class="phase-id">${esc(phase.id)}</span>
          <span class="status-pill">${esc(phase.status)}</span>
        </div>
        <h3>${esc(phase.title)}</h3>
        <p>${esc(phase.focus)}</p>
        <div class="mini-progress"><span style="width:${phase.progress}%"></span></div>
        <div class="doc-tags">
          ${phase.docs.map((doc) => `<span>${esc(doc)}</span>`).join("")}
        </div>
      </article>
    `).join("");
  }

  function renderArchitecture() {
    byId("architecture-flow").innerHTML = state.architecture.map((layer, index) => `
      <div class="architecture-node ${toneClass(layer.tone)}">
        <div>
          <span class="node-index">${String(index + 1).padStart(2, "0")}</span>
          <h3>${esc(layer.title)}</h3>
          <p>${esc(layer.detail)}</p>
        </div>
      </div>
    `).join("");
  }

  function renderDocs() {
    byId("doc-health").innerHTML = state.docs.map((doc) => `
      <a class="doc-row ${toneClass(doc.status)}" href="../${esc(doc.path)}">
        <span>
          <strong>${esc(doc.name)}</strong>
          <small>${esc(doc.path)}</small>
        </span>
        <em>${esc(doc.status)}</em>
        <b>${esc(doc.signal)}</b>
      </a>
    `).join("");
  }

  function renderRisks() {
    byId("risk-list").innerHTML = state.risks.map((risk) => `
      <article class="stack-item severity-${esc(risk.severity)}">
        <div>
          <strong>${esc(risk.title)}</strong>
          <span>${esc(risk.control)}</span>
        </div>
        <em>${esc(risk.severity)}</em>
      </article>
    `).join("");
  }

  function renderDecisions() {
    byId("decision-list").innerHTML = state.decisions.map((decision) => `
      <a class="stack-item decision" href="${esc(decision.path)}">
        <div>
          <strong>${esc(decision.id)} · ${esc(decision.title)}</strong>
          <span>${esc(decision.path.replace("../", ""))}</span>
        </div>
        <em>${esc(decision.status)}</em>
      </a>
    `).join("");
  }

  function renderDataSources() {
    byId("source-plan").innerHTML = state.dataSources.map((source) => `
      <article class="plan-card ${toneClass(source.status)}">
        <div class="plan-card-top">
          <strong>${esc(source.name)}</strong>
          <em>${esc(source.status)}</em>
        </div>
        <dl>
          <div><dt>阶段</dt><dd>${esc(source.phase)}</dd></div>
          <div><dt>敏感级别</dt><dd>${esc(source.sensitivity)}</dd></div>
          <div><dt>下一步</dt><dd>${esc(source.next)}</dd></div>
        </dl>
      </article>
    `).join("");
  }

  function renderCapabilities() {
    byId("capability-plan").innerHTML = state.capabilities.map((capability) => `
      <article class="plan-card ${toneClass(capability.status)}">
        <div class="plan-card-top">
          <strong>${esc(capability.name)}</strong>
          <em>${esc(capability.status)}</em>
        </div>
        <dl>
          <div><dt>阶段</dt><dd>${esc(capability.phase)}</dd></div>
          <div><dt>风险</dt><dd>${esc(capability.risk)}</dd></div>
          <div><dt>护栏</dt><dd>${esc(capability.guardrail)}</dd></div>
        </dl>
      </article>
    `).join("");
  }

  function renderOpenQuestions() {
    byId("open-questions").innerHTML = state.openQuestions.map((question) => `
      <article class="stack-item">
        <div>
          <strong>${esc(question.title)}</strong>
          <span>${esc(question.detail)}</span>
        </div>
      </article>
    `).join("");
  }

  function renderRecentChanges() {
    byId("recent-changes").innerHTML = state.recentChanges.map((change) => `
      <article class="stack-item change-item">
        <div>
          <strong>${esc(change.date)} · ${esc(change.title)}</strong>
          <span>${esc(change.detail)}</span>
        </div>
      </article>
    `).join("");
  }

  function renderSync() {
    byId("sync-checklist").innerHTML = state.syncChecklist.map((item) => `
      <div class="sync-item">
        <span aria-hidden="true"></span>
        <p>${esc(item)}</p>
      </div>
    `).join("");
  }

  renderOverview();
  renderWork();
  renderPhases();
  renderArchitecture();
  renderDocs();
  renderRisks();
  renderDecisions();
  renderDataSources();
  renderCapabilities();
  renderOpenQuestions();
  renderRecentChanges();
  renderSync();
})();
