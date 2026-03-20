class MedicationTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._medications = [];
    this._hass = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._buildMedications();
    this._render();
  }

  setConfig(config) {
    this._config = config || {};
  }

  _buildMedications() {
    if (!this._hass) return;
    const states = this._hass.states;

    const nextDoseSensors = Object.entries(states).filter(
      ([id]) => id.startsWith("sensor.") && id.endsWith("_next_dose")
    );

    // Also find PRN medications via next_available sensors
    const nextAvailableSensors = Object.entries(states).filter(
      ([id]) => id.startsWith("sensor.") && id.endsWith("_next_available")
    );

    const scheduledMeds = nextDoseSensors.map(([entityId, state]) => {
      const base = entityId.replace("sensor.", "").replace("_next_dose", "");
      const friendlyBase = state.attributes.friendly_name?.replace(/\s*Next Dose$/i, "") || base;
      const get = (domain, suffix) => states[`${domain}.${base}_${suffix}`] || null;
      return {
        name: friendlyBase,
        base,
        med_type: "scheduled",
        next_dose: state,
        last_taken: get("sensor", "last_taken"),
        streak: get("sensor", "streak"),
        taken_today: get("sensor", "taken_today"),
        overdue: get("binary_sensor", "overdue"),
        due_soon: get("binary_sensor", "due_soon"),
        btn_taken: get("button", "mark_taken"),
        btn_skipped: get("button", "mark_skipped"),
      };
    });

    const prnMeds = nextAvailableSensors.map(([entityId, state]) => {
      const base = entityId.replace("sensor.", "").replace("_next_available", "");
      const friendlyBase = state.attributes.friendly_name?.replace(/\s*Next Available$/i, "") || base;
      const get = (domain, suffix) => states[`${domain}.${base}_${suffix}`] || null;
      return {
        name: friendlyBase,
        base,
        med_type: "prn",
        next_available: state,
        available: get("binary_sensor", "available"),
        last_taken: get("sensor", "last_taken"),
        streak: get("sensor", "streak"),
        taken_today: get("sensor", "taken_today"),
        btn_taken: get("button", "mark_taken"),
        btn_skipped: get("button", "mark_skipped"),
      };
    });

    this._medications = [...scheduledMeds, ...prnMeds];
  }

  _formatRelative(isoStr) {
    if (!isoStr || isoStr === "unavailable" || isoStr === "unknown") return "—";
    try {
      const d = new Date(isoStr);
      if (isNaN(d)) return "—";
      const now = new Date();
      const diffMin = Math.round((d - now) / 60000);
      if (diffMin > 0 && diffMin < 120) return `in ${diffMin}m`;
      if (diffMin <= 0 && diffMin > -120) return `${Math.abs(diffMin)}m ago`;
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch { return "—"; }
  }

  _renderScheduledMed(med) {
    const isOverdue = med.overdue?.state === "on";
    const isDueSoon = med.due_soon?.state === "on";
    let rowClass = "med-row";
    let badge = `<span class="status-badge badge-ok">On track</span>`;
    if (isOverdue) { rowClass += " overdue"; badge = `<span class="status-badge badge-overdue">Overdue</span>`; }
    else if (isDueSoon) { rowClass += " due-soon"; badge = `<span class="status-badge badge-due-soon">Due soon</span>`; }

    const nextDose = this._formatRelative(med.next_dose?.state);
    const lastTaken = this._formatRelative(med.last_taken?.state);
    const streak = med.streak?.state ?? "0";
    const takenToday = med.taken_today?.state ?? "0";
    const scheduledToday = med.taken_today?.attributes?.doses_scheduled_today ?? "?";
    const btnTakenId = med.btn_taken ? `button.${med.base}_mark_taken` : null;
    const btnSkippedId = med.btn_skipped ? `button.${med.base}_mark_skipped` : null;

    return `
      <div class="${rowClass}">
        <div class="med-name">${med.name}${badge}</div>
        <div class="stats">
          <div class="stat"><span class="stat-label">Next dose</span><span class="stat-value">${nextDose}</span></div>
          <div class="stat"><span class="stat-label">Last taken</span><span class="stat-value">${lastTaken}</span></div>
          <div class="stat"><span class="stat-label">Streak</span><span class="stat-value">${streak} day${streak === "1" ? "" : "s"}</span></div>
          <div class="stat"><span class="stat-label">Taken today</span><span class="stat-value">${takenToday} / ${scheduledToday}</span></div>
        </div>
        <div class="actions">
          ${btnTakenId ? `<button class="btn btn-taken" data-entity="${btnTakenId}">Mark taken</button>` : ""}
          ${btnSkippedId ? `<button class="btn btn-skipped" data-entity="${btnSkippedId}">Skip dose</button>` : ""}
        </div>
      </div>
    `;
  }

  _renderPrnMed(med) {
    const isAvailable = med.available?.state === "on";
    const nextAvailableStr = med.next_available?.state;
    const maxPerDay = med.next_available?.attributes?.prn_max_per_day ?? "?";
    const takenToday = med.taken_today?.state ?? "0";
    const lastTaken = this._formatRelative(med.last_taken?.state);
    const btnTakenId = med.btn_taken ? `button.${med.base}_mark_taken` : null;

    let rowClass = "med-row";
    let badge;
    let availabilityInfo;

    if (isAvailable) {
      rowClass += " available";
      badge = `<span class="status-badge badge-ok">Available now</span>`;
      availabilityInfo = "Take when needed";
    } else if (!nextAvailableStr || nextAvailableStr === "unavailable" || nextAvailableStr === "unknown") {
      badge = `<span class="status-badge badge-limit">Limit reached</span>`;
      availabilityInfo = "Daily limit reached";
    } else {
      rowClass += " prn-waiting";
      const countdown = this._formatCountdown(nextAvailableStr);
      badge = `<span class="status-badge badge-waiting">Available ${countdown}</span>`;
      availabilityInfo = `Next available ${countdown}`;
    }

    return `
      <div class="${rowClass}">
        <div class="med-name">${med.name}<span class="prn-tag">PRN</span>${badge}</div>
        <div class="stats">
          <div class="stat"><span class="stat-label">Availability</span><span class="stat-value">${availabilityInfo}</span></div>
          <div class="stat"><span class="stat-label">Last taken</span><span class="stat-value">${lastTaken}</span></div>
          <div class="stat"><span class="stat-label">Taken today</span><span class="stat-value">${takenToday} / ${maxPerDay}</span></div>
        </div>
        <div class="actions">
          ${btnTakenId ? `<button class="btn btn-taken${isAvailable ? "" : " btn-disabled"}" data-entity="${btnTakenId}" ${isAvailable ? "" : "disabled"}>Mark taken</button>` : ""}
        </div>
      </div>
    `;
  }

  _formatCountdown(isoStr) {
    if (!isoStr || isoStr === "unavailable" || isoStr === "unknown") return "—";
    try {
      const d = new Date(isoStr);
      if (isNaN(d)) return "—";
      const now = new Date();
      const diffMin = Math.round((d - now) / 60000);
      if (diffMin <= 0) return "now";
      if (diffMin < 60) return `in ${diffMin}m`;
      const h = Math.floor(diffMin / 60);
      const m = diffMin % 60;
      return m > 0 ? `in ${h}h ${m}m` : `in ${h}h`;
    } catch { return "—"; }
  }

  async _callButton(entityId) {
    if (!this._hass) return;
    await this._hass.callService("button", "press", { entity_id: entityId });
  }

  _render() {
    if (!this.shadowRoot) return;

    const style = `
      :host { display: block; }
      .card { background: var(--card-background-color, #fff); border-radius: 12px; padding: 16px; }
      .card-header { font-size: 16px; font-weight: 500; color: var(--primary-text-color); margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
      .med-row { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
      .med-row:last-child { margin-bottom: 0; }
      .med-row.overdue { border-color: var(--error-color, #db4437); background: rgba(219,68,55,0.06); }
      .med-row.due-soon { border-color: var(--warning-color, #ffa600); background: rgba(255,166,0,0.06); }
      .med-name { font-size: 15px; font-weight: 500; color: var(--primary-text-color); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
      .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 500; }
      .badge-overdue { background: var(--error-color, #db4437); color: white; }
      .badge-due-soon { background: var(--warning-color, #ffa600); color: white; }
      .badge-ok { background: var(--success-color, #43a047); color: white; }
      .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; margin-bottom: 10px; }
      .stat { display: flex; flex-direction: column; }
      .stat-label { font-size: 11px; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.04em; }
      .stat-value { font-size: 13px; color: var(--primary-text-color); font-weight: 500; }
      .actions { display: flex; gap: 8px; margin-top: 8px; }
      .btn { flex: 1; padding: 7px 0; border-radius: 6px; border: none; font-size: 13px; font-weight: 500; cursor: pointer; transition: opacity 0.15s; }
      .btn:active { opacity: 0.7; }
      .btn-taken { background: var(--primary-color, #03a9f4); color: white; }
      .btn-skipped { background: var(--secondary-background-color, #f5f5f5); color: var(--primary-text-color); border: 1px solid var(--divider-color, #e0e0e0); }
      .empty { text-align: center; color: var(--secondary-text-color); padding: 24px; font-size: 14px; line-height: 1.6; }
      .med-row.available { border-color: var(--success-color, #43a047); background: rgba(67,160,71,0.06); }
      .med-row.prn-waiting { border-color: var(--warning-color, #ffa600); background: rgba(255,166,0,0.06); }
      .prn-tag { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: var(--secondary-background-color); color: var(--secondary-text-color); border: 1px solid var(--divider-color); font-weight: 500; }
      .badge-waiting { background: var(--warning-color, #ffa600); color: white; }
      .badge-limit { background: var(--error-color, #db4437); color: white; }
      .btn-disabled { opacity: 0.4; cursor: not-allowed; }
    `;

    let rows;
    if (this._medications.length === 0) {
      rows = `<div class="empty">No medications found.<br>Add medications via the integration settings.</div>`;
    } else {
      rows = this._medications.map(med => {
        if (med.med_type === "prn") {
          return this._renderPrnMed(med);
        }
        return this._renderScheduledMed(med);
      }).join("");
    }

    this.shadowRoot.innerHTML = `
      <style>${style}</style>
      <div class="card">
        <div class="card-header">💊 Medications</div>
        ${rows}
      </div>
    `;

    this.shadowRoot.querySelectorAll(".btn[data-entity]").forEach(btn => {
      btn.addEventListener("click", () => this._callButton(btn.dataset.entity));
    });
  }

  getCardSize() {
    return 1 + this._medications.length * 2;
  }

  static getStubConfig() {
    return {};
  }
}

customElements.define("medication-tracker-card", MedicationTrackerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "medication-tracker-card",
  name: "Medication Tracker",
  description: "Shows all medications with status and mark taken / skip buttons.",
  preview: false,
});
