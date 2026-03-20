class MedicationTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._medications = [];
    this._hass = null;
    this._updateInterval = null;
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
    const meds = {};

    for (const [entityId, state] of Object.entries(states)) {
      if (!entityId.startsWith("sensor.") && !entityId.startsWith("binary_sensor.") && !entityId.startsWith("button.")) continue;
      const attr = state.attributes;
      const medId = attr.medication_id;
      if (!medId) continue;
      if (!meds[medId]) meds[medId] = { id: medId, name: attr.friendly_name || entityId, entities: {} };

      if (entityId.includes("_next_dose")) meds[medId].entities.next_dose = state;
      else if (entityId.includes("_last_taken")) meds[medId].entities.last_taken = state;
      else if (entityId.includes("_streak")) meds[medId].entities.streak = state;
      else if (entityId.includes("_taken_today")) meds[medId].entities.taken_today = state;
      else if (entityId.includes("_overdue")) meds[medId].entities.overdue = state;
      else if (entityId.includes("_due_soon")) meds[medId].entities.due_soon = state;
      else if (entityId.includes("_mark_taken")) meds[medId].entities.btn_taken = { entityId, state };
      else if (entityId.includes("_mark_skipped")) meds[medId].entities.btn_skipped = { entityId, state };
    }

    // Use sensor name as med name (strip suffix)
    for (const med of Object.values(meds)) {
      if (med.entities.next_dose) {
        med.name = med.entities.next_dose.attributes.friendly_name
          ?.replace(" Next Dose", "") || med.name;
      }
    }

    this._medications = Object.values(meds);
  }

  _formatTime(isoStr) {
    if (!isoStr || isoStr === "unavailable" || isoStr === "unknown") return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch { return "—"; }
  }

  _formatRelative(isoStr) {
    if (!isoStr || isoStr === "unavailable" || isoStr === "unknown") return "—";
    try {
      const d = new Date(isoStr);
      const now = new Date();
      const diffMin = Math.round((d - now) / 60000);
      if (diffMin > 0 && diffMin < 120) return `in ${diffMin}m`;
      if (diffMin < 0 && diffMin > -120) return `${Math.abs(diffMin)}m ago`;
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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
      .card-header ha-icon { color: var(--primary-color); }
      .med-row { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
      .med-row:last-child { margin-bottom: 0; }
      .med-row.overdue { border-color: var(--error-color, #db4437); background: var(--error-color, #db443710); }
      .med-row.due-soon { border-color: var(--warning-color, #ffa600); background: var(--warning-color, #ffa60010); }
      .med-name { font-size: 15px; font-weight: 500; color: var(--primary-text-color); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
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
      .empty { text-align: center; color: var(--secondary-text-color); padding: 24px; font-size: 14px; }
    `;

    const rows = this._medications.length === 0
      ? `<div class="empty">No medications found.<br>Add medications via the integration settings.</div>`
      : this._medications.map(med => {
          const isOverdue = med.entities.overdue?.state === "on";
          const isDueSoon = med.entities.due_soon?.state === "on";
          const nextDose = this._formatRelative(med.entities.next_dose?.state);
          const lastTaken = this._formatRelative(med.entities.last_taken?.state);
          const streak = med.entities.streak?.state ?? "0";
          const takenToday = med.entities.taken_today?.state ?? "0";
          const scheduledToday = med.entities.taken_today?.attributes?.doses_scheduled_today ?? "?";

          let rowClass = "med-row";
          let badge = `<span class="status-badge badge-ok">On track</span>`;
          if (isOverdue) {
            rowClass += " overdue";
            badge = `<span class="status-badge badge-overdue">Overdue</span>`;
          } else if (isDueSoon) {
            rowClass += " due-soon";
            badge = `<span class="status-badge badge-due-soon">Due soon</span>`;
          }

          const btnTakenId = med.entities.btn_taken?.entityId;
          const btnSkippedId = med.entities.btn_skipped?.entityId;

          return `
            <div class="${rowClass}">
              <div class="med-name">
                ${med.name}
                ${badge}
              </div>
              <div class="stats">
                <div class="stat">
                  <span class="stat-label">Next dose</span>
                  <span class="stat-value">${nextDose}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Last taken</span>
                  <span class="stat-value">${lastTaken}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Streak</span>
                  <span class="stat-value">${streak} day${streak === "1" ? "" : "s"}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Taken today</span>
                  <span class="stat-value">${takenToday} / ${scheduledToday}</span>
                </div>
              </div>
              <div class="actions">
                ${btnTakenId ? `<button class="btn btn-taken" data-entity="${btnTakenId}">Mark taken</button>` : ""}
                ${btnSkippedId ? `<button class="btn btn-skipped" data-entity="${btnSkippedId}">Skip dose</button>` : ""}
              </div>
            </div>
          `;
        }).join("");

    this.shadowRoot.innerHTML = `
      <style>${style}</style>
      <div class="card">
        <div class="card-header">
          <ha-icon icon="mdi:pill"></ha-icon>
          Medications
        </div>
        ${rows}
      </div>
    `;

    // Attach button listeners
    this.shadowRoot.querySelectorAll(".btn[data-entity]").forEach(btn => {
      btn.addEventListener("click", () => this._callButton(btn.dataset.entity));
    });
  }

  getCardSize() {
    return 1 + this._medications.length * 2;
  }

  static getConfigElement() {
    return document.createElement("medication-tracker-card-editor");
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
