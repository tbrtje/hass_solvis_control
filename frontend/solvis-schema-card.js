/**
 * SolvisLeo 180 Anlagenschema. Self-contained Lovelace module; no cloud requests.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
(() => {
  const VIEWS = { heating: "Heizung", water: "Warmwasser", heatpump: "Wärmepumpe" };
  const COLORS = { warm: "#ffd24d", hot: "#ffff54", cold: "#3d96c9" };
  const escape = (value) => String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const UNAVAILABLE = new Set(["unknown", "unavailable", ""]);

  class SolvisSchemaCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (event) => this._activate(event));
      this.shadowRoot.addEventListener("keydown", (event) => {
        if ((event.key === "Enter" || event.key === " ") && event.target.closest("[data-entity]")) {
          event.preventDefault();
          this._activate(event);
        }
      });
    }

    setConfig(config) {
      if (!config.entities || typeof config.entities !== "object" || Array.isArray(config.entities)) {
        throw new Error("Bitte entities mit den Fühlern und Aktoren der Anlage konfigurieren.");
      }
      if (config.view && !Object.hasOwn(VIEWS, config.view)) {
        throw new Error("view muss heating, water oder heatpump sein.");
      }
      for (const entity of Object.values(config.entities)) {
        if (typeof entity !== "string" || !/^[a-z_]+\.[a-z0-9_]+$/.test(entity)) {
          throw new Error("Jede Zuordnung unter entities muss eine gültige entity_id sein.");
        }
      }
      this._config = { ...config, entities: { ...config.entities } };
      this._view = config.view || "heating";
      this._render();
    }

    set hass(hass) {
      const previous = this._hass;
      this._hass = hass;
      if (!this._config) return;
      if (!previous || previous.locale?.language !== hass.locale?.language ||
          previous.language !== hass.language || previous.connected !== hass.connected ||
          Object.values(this._config.entities).some((id) => previous.states[id] !== hass.states[id])) {
        this._render();
      }
    }

    getCardSize() { return 9; }
    getGridOptions() { return { columns: "full", rows: "auto", min_columns: 12 }; }

    _state(key) {
      if (this._hass?.connected === false) return undefined;
      const state = this._hass?.states[this._config.entities[key]];
      return state && !UNAVAILABLE.has(state.state) ? state : undefined;
    }

    _measurement(key, targetUnit, precision = 1) {
      const state = this._state(key);
      if (!state || !String(state.state).trim()) return "—";
      let value = Number(state.state);
      if (!Number.isFinite(value)) return "—";
      let unit = state.attributes?.unit_of_measurement || targetUnit;
      const conversions = {
        "W:kW": (v) => v / 1000,
        "l/min:l/h": (v) => v * 60,
        "l/h:l/min": (v) => v / 60,
        "m³/h:l/h": (v) => v * 1000,
        "m³/h:l/min": (v) => v * 1000 / 60,
        "°F:°C": (v) => (v - 32) * 5 / 9,
        "Pa:bar": (v) => v / 100000,
        "kPa:bar": (v) => v / 100,
      };
      if (unit !== targetUnit && conversions[`${unit}:${targetUnit}`]) {
        value = conversions[`${unit}:${targetUnit}`](value);
        unit = targetUnit;
      }
      const locale = this._hass?.locale?.language || this._hass?.language || "de";
      const number = new Intl.NumberFormat(locale, {
        minimumFractionDigits: precision, maximumFractionDigits: precision,
      }).format(value);
      return `${number} ${unit}`;
    }

    _status(key) {
      const state = this._state(key)?.state;
      return state === "on" ? "Ein" : state === "off" ? "Aus" : "Nicht verfügbar";
    }

    _binding(key, label) {
      const id = this._config.entities[key];
      return id ? `data-entity="${escape(id)}" role="button" tabindex="0" aria-label="${escape(label)}: Details öffnen"` : "";
    }

    _sensor(key, x, y, label, color = "warm", side = "right") {
      const value = this._measurement(key, "°C");
      const left = side === "left";
      const above = side === "above";
      const below = side === "below";
      const textX = x + (above || below ? 0 : left ? -18 : 18);
      const anchor = above || below ? "middle" : left ? "end" : "start";
      return `<g class="sensor ${value === "—" ? "missing" : ""}" ${this._binding(key, `${label}: ${value}`)}>
        <title>${escape(label)}: ${escape(value)}</title>
        <circle cx="${x}" cy="${y}" r="9" fill="${COLORS[color]}"/>
        <text class="reading" x="${textX}" y="${y + (above ? -18 : below ? 39 : 7)}" text-anchor="${anchor}">${escape(value)}</text>
        <text class="caption" x="${textX}" y="${y + (below ? 59 : 25)}" text-anchor="${anchor}">${escape(label)}</text>
      </g>`;
    }

    _pump(key, x, y, label, rotation = 0, showStatus = true) {
      const active = this._state(key)?.state === "on";
      const known = ["on", "off"].includes(this._state(key)?.state);
      return `<g class="pump ${known ? "" : "missing"}" ${this._binding(key, label)}>
        <title>${escape(label)}: ${this._status(key)}</title>
        <g transform="translate(${x} ${y}) rotate(${rotation})">
          <circle r="19" fill="white"/>
          <g class="${active ? "running" : ""}"><path d="M-8 -15 L15 0 L-8 15 Z" fill="${active ? "#1c1c1f" : "#b7b7b9"}" stroke="none"/></g>
        </g>
        ${showStatus ? `<text class="caption" x="${x + 30}" y="${y + 4}">${escape(this._status(key))}</text>` : ""}
      </g>`;
    }

    _tank() {
      return `<g class="equipment">
        <rect x="205" y="145" width="155" height="350" fill="white"/>
        <path d="M249 169 H316 L321 174 V214 Q286 236 244 214 V174 Z" fill="#8a8a8a" stroke-width="1.5"/>
        <path d="M250 176 H315 V211 L300 218 H265 L250 211 Z" fill="none" stroke-width="1"/>
        ${Array.from({ length: 8 }, (_, i) => `<path d="M${246 + i * 10} ${242 + (i === 0 || i === 7 ? 0 : 7)} V494" stroke="#777" stroke-width="3"/>`).join("")}
        <path d="M225 496 H239 M326 496 H340" stroke-width="3"/>
        <text class="caption" x="282" y="527" text-anchor="middle">SolvisLeo 180 · Schichtenspeicher</text>
      </g>
      ${this._sensor("s1", 205, 175, "S1 · Speicher oben", "hot", "left")}
      ${this._sensor("s4", 205, 325, "S4 · Puffer oben", "warm", "left")}
      ${this._sensor("s9", 205, 477, "S9 · Puffer unten", "cold", "left")}`;
    }

    _outdoor() {
      return `<g class="equipment" transform="translate(940 65)">
        <path d="M0 25 L25 0 L50 25 M7 18 V43 H42 V18 M22 43 V29 H30 V43" fill="none"/>
      </g>${this._sensor("s10", 925, 88, "S10 · Außen", "cold", "left")}`;
    }

    _heating() {
      return `${this._outdoor()}
        <g class="pipes"><path d="M360 470 H430 V265 M360 483 H572 V265 M430 400 H572"/></g>
        <g class="equipment">
          <text class="diagram-label" x="460" y="172" text-anchor="middle">Heizkreis 1</text>
          <rect x="410" y="190" width="183" height="75" fill="white"/>
          ${Array.from({ length: 9 }, (_, i) => `<path d="M${424 + i * 19} 198 V257"/>`).join("")}
          <path d="M430 384 L440 401 L420 401 Z M430 418 L440 401 L420 401 Z M447 391 L430 401 L447 411 Z" fill="white"/>
        </g>
        ${this._pump("heating_pump", 430, 320, "HKR1 · Pumpe", -90)}
        ${this._sensor("s12", 430, 365, "S12 · Vorlauf HKR1", "cold")}
        <text class="caption" x="620" y="402">Mischer HKR1</text>
        <text class="caption" x="620" y="424">Auf: ${this._status("mixer_open")} · Zu: ${this._status("mixer_close")}</text>`;
    }

    _water() {
      return `<g class="pipes"><path d="M360 388 H586 V294 H878 V250 M360 482 H981 M878 294 V482 M452 388 V482"/></g>
        <g class="equipment">
          <path d="M439 380 L453 388 L439 397 Z M466 380 L453 388 L466 397 Z M445 405 L453 388 L461 405 Z" fill="white"/>
          <rect x="514" y="372" width="37" height="130" fill="white"/>
          <path d="M514 372 L551 502"/>
          <rect x="858" y="198" width="38" height="95" fill="white"/>
          <path d="M896 215 H955 V237 H896 M930 237 V248 H951 V237 M858 180 H896 V193 H858 Z M896 183 H935 V189 H896" fill="white"/>
          <circle cx="650" cy="482" r="13" fill="white"/><path d="M644 476 L656 488 M644 488 L656 476 M981 482 L997 466 M981 482 L997 498"/>
          <rect x="870" y="425" width="16" height="29" fill="white"/><path d="M870 425 L886 454"/>
          <text class="caption" x="532" y="527" text-anchor="middle">Wärmetauscher</text>
          <text class="caption" x="878" y="163" text-anchor="middle">Warmwasser</text>
        </g>
        ${this._pump("circulation_pump", 878, 386, "Zirkulationspumpe", 90)}
        <g class="equipment" ${this._binding("water_pump_modulation", "Warmwasserpumpe")}>
          <circle cx="495" cy="388" r="18" fill="white"/><path d="M487 374 L509 388 L487 402 Z" fill="#1c1c1f" stroke="none"/>
          <text class="reading" x="495" y="340" text-anchor="middle">${escape(this._measurement("water_pump_modulation", "%", 0))}</text>
          <text class="caption" x="495" y="357" text-anchor="middle">Pumpe O5</text>
        </g>
        ${this._sensor("s2", 586, 326, "S2 · Warmwasser", "warm")}
        ${this._sensor("s11", 878, 326, "S11 · Zirkulation", "cold")}
        ${this._sensor("s15", 760, 482, "S15 · Kaltwasser", "cold", "above")}`;
    }

    _heatpump() {
      const smartGrid = this._state("smart_grid")?.state || "Nicht verfügbar";
      const pressure = this._measurement("pressure", "bar");
      const volumeFlow = this._measurement("heatpump_volume_flow", "l/min");
      const modulation = this._measurement("charging_modulation", "%", 0);
      const thermalPower = this._measurement("heatpump_power_thermal", "kW");
      const electricPower = this._measurement("heatpump_power_electric", "kW");
      return `${this._outdoor()}
        <g class="equipment" ${this._binding("smart_grid", `Smart Grid: ${smartGrid}`)}>
          <rect x="470" y="55" width="245" height="82" rx="15" fill="#1c1c1f"/>
          <path d="M471 92 H714 V121 Q714 136 699 136 H486 Q471 136 471 121 Z" fill="white" stroke="none"/>
          <text class="smart-grid-title" x="592.5" y="81" text-anchor="middle">Smart Grid</text>
          <text class="smart-grid-value" x="592.5" y="120" text-anchor="middle">${escape(smartGrid)}</text>
        </g>
        <g class="pipes">
          <path d="M360 350 H395 M425 350 H760 M360 446 H760"/>
          <path d="M360 310 H410 V430" stroke="#b5b5b8" stroke-width="3" stroke-dasharray="3 4"/>
        </g>
        <g class="equipment">
          <g><title>Umschaltventil</title>
            <path d="M394 436 L410 446 L394 456 Z M426 436 L410 446 L426 456 Z" fill="#1c1c1f"/>
            <path d="M402 430 L410 446 L418 430 Z" fill="white" stroke="#b5b5b8"/>
          </g>
          <path d="M760 297 Q870 290 980 297 V480 H760 Z" fill="white" stroke-width="2.8"/>
          <path d="M838 299 V479"/>
          ${Array.from({ length: 32 }, (_, i) => `<path d="M839 ${302 + i * 5.5} H979" stroke-width="1.6"/>`).join("")}
          <path d="M760 480 H980 V490 H760 Z M767 490 V500 H778 V490 M962 490 V500 H973 V490" fill="#1c1c1f"/>
          <circle cx="800" cy="350" r="18" fill="white"/>
          <path d="M788 361 L800 333 L812 361 Z" fill="#1c1c1f" stroke="none"/>
          <rect x="789" y="402" width="23" height="40" fill="white"/>
          <path d="M806 409 L795 420 H805 L795 435" fill="none" stroke-width="3"/>
          <text class="diagram-label" x="870" y="276" text-anchor="middle">Wärmepumpe</text>
        </g>
        <g class="equipment" ${this._binding("pressure", `Anlagendruck: ${pressure}`)}>
          <circle cx="610" cy="350" r="8" fill="${pressure === "—" ? "#d9d9dd" : "#1c1c1f"}"/>
          <text class="reading" x="610" y="389" text-anchor="middle">${escape(pressure)}</text>
          <text class="caption" x="610" y="409" text-anchor="middle">Anlagendruck</text>
        </g>
        <g class="equipment" ${this._binding("heatpump_volume_flow", `Volumenstrom Wärmepumpe: ${volumeFlow}`)}>
          <circle cx="510" cy="446" r="12" fill="white"/>
          <path d="M504 440 L516 452 M504 452 L516 440"/>
          <text class="reading" x="510" y="485" text-anchor="middle">${escape(volumeFlow)}</text>
          <text class="caption" x="510" y="505" text-anchor="middle">Volumenstrom</text>
        </g>
        ${this._pump("charging_pump", 610, 446, "Ladepumpe A2", 180, false)}
        ${this._sensor("heatpump_flow_temp", 705, 350, "Vorlauf", "cold", "below")}
        ${this._sensor("heatpump_return_temp", 705, 446, "Rücklauf", "cold", "below")}
        <g ${this._binding("charging_modulation", `Ladepumpe O4: ${modulation}`)}>
          <text class="reading" x="610" y="485" text-anchor="middle">${escape(modulation)}</text>
          <text class="caption" x="610" y="505" text-anchor="middle">Ladepumpe O4</text>
        </g>
        <g ${this._binding("heatpump_power_thermal", `Thermische Leistung: ${thermalPower}`)}>
          <text class="reading" x="1040" y="346" text-anchor="middle">${escape(thermalPower)}</text>
          <text class="caption" x="1040" y="368" text-anchor="middle">Pth · thermisch</text>
        </g>
        <g ${this._binding("heatpump_power_electric", `Elektrische Aufnahme: ${electricPower}`)}>
          <text class="reading" x="1040" y="405" text-anchor="middle">${escape(electricPower)}</text>
          <text class="caption" x="1040" y="427" text-anchor="middle">Pel · elektrisch</text>
        </g>
        <g ${this._binding("heizstab_status", "Heizstab")}>
          <text class="heatpump-status" x="1040" y="465" text-anchor="middle">${this._status("heizstab_status")}</text>
          <text class="caption" x="1040" y="487" text-anchor="middle">Heizstab</text>
        </g>`;
    }

    _metrics() {
      const metrics = {
        heating: [["heating_flow", "Vorlauf · WMZ", "°C"], ["heating_return", "Rücklauf · WMZ", "°C"], ["heating_volume_flow", "Volumenstrom · WMZ", "l/h", 0], ["heating_power", "Thermische Leistung · WMZ", "kW"]],
        water: [["s2", "Warmwasser · S2", "°C"], ["s11", "Zirkulation · S11", "°C"], ["water_flow", "Volumenstrom · S18", "l/min"], ["water_power", "Thermische Leistung", "kW"]],
        heatpump: [["heatpump_power_thermal", "Thermische Leistung · Pth", "kW"], ["heatpump_power_electric", "Elektrische Aufnahme · Pel", "kW"], ["charging_modulation", "Ladepumpe · O4", "%", 0], ["heatpump_volume_flow", "Volumenstrom Wärmepumpe", "l/min"]],
      };
      return metrics[this._view].map(([key, label, unit, precision]) => {
        const value = this._measurement(key, unit, precision ?? 1);
        return `<button class="metric ${value === "—" ? "unavailable" : ""}" type="button" ${this._config.entities[key] ? this._binding(key, `${label}: ${value}`) : "disabled"}>
          <span class="metric-label">${escape(label)}</span><span class="metric-value">${escape(value)}</span>
        </button>`;
      }).join("");
    }

    _activate(event) {
      const target = event.target.closest("[data-view], [data-entity]");
      if (target?.dataset.view) {
        this._view = target.dataset.view;
        this._render();
        this.shadowRoot.querySelector(`[data-view="${this._view}"]`)?.focus();
      } else if (target?.dataset.entity) {
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          detail: { entityId: target.dataset.entity }, bubbles: true, composed: true,
        }));
      }
    }

    _render() {
      if (!this._config) return;
      const views = Object.keys(VIEWS);
      const navigation = this._config.navigation !== false;
      const index = views.indexOf(this._view);
      const unavailable = [
        ["heatpump_flow_temp", "Vorlauf Wärmepumpe"], ["heatpump_return_temp", "Rücklauf Wärmepumpe"],
        ["heatpump_volume_flow", "Volumenstrom Wärmepumpe"], ["pressure", "Anlagendruck"], ["smart_grid", "Smart Grid"],
      ].filter(([key]) => !this._state(key)).map(([, label]) => label);
      this.shadowRoot.innerHTML = `<style>
        :host { display: block; min-width: 0; container: schema / inline-size; }
        * { box-sizing: border-box; }
        ha-card { display: block; background: #fff; color: #1c1c1f; border-radius: 12px; overflow: hidden; font-family: Arial, Helvetica, sans-serif; }
        header { padding: 26px 28px 18px; border-bottom: 1px solid #ececee; }
        .eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1.7px; color: #6f6f73; margin-bottom: 8px; }
        h2 { font-size: 24px; line-height: 1.25; margin: 0; font-weight: 650; }
        h2::before { content: ''; display: inline-block; width: 4px; height: 23px; background: #d33e1b; margin-right: 12px; vertical-align: -3px; }
        .metrics { display: grid; grid-template-columns: repeat(4, 1fr); border: 2px solid #222; border-radius: 11px; margin: 24px 28px 0; overflow: hidden; }
        button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; }
        button:disabled { cursor: default; opacity: 1; }
        button:focus-visible, [data-entity]:focus-visible { outline: 3px solid #d33e1b; outline-offset: -3px; }
        .metric { padding: 13px 16px; text-align: left; border-right: 1px solid #e5e5e7; }
        .metric:last-child { border-right: 0; }
        .metric-label { display: block; font-size: 11px; color: #6f6f73; margin-bottom: 6px; line-height: 1.3; }
        .metric-value { font-size: 24px; white-space: nowrap; }
        .unavailable .metric-value { color: #888; }
        .drawing { overflow-x: auto; overscroll-behavior-x: contain; }
        svg { display: block; width: 100%; min-width: 900px; max-width: 1320px; margin: 0 auto; color: #1c1c1f; }
        .equipment, .sensor, .pump { stroke: #1c1c1f; stroke-width: 2.2; }
        .pipes { fill: none; stroke: #1c1c1f; stroke-width: 3.6; stroke-linecap: square; }
        svg text { stroke: none; fill: #1c1c1f; font-weight: 400; }
        .reading { font-size: 23px; }
        .diagram-label { font-size: 21px; }
        .caption { font-size: 14px; fill: #707075; }
        .smart-grid-title { font-size: 20px; font-weight: 600; fill: white; }
        .smart-grid-value { font-size: 19px; }
        .heatpump-status { font-size: 16px; }
        [data-entity] { cursor: pointer; }
        .missing circle { fill: #d9d9dd; }
        .missing .reading { fill: #888; }
        .running { animation: spin 3s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        nav { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 8px 16px 20px; }
        nav button { padding: 12px 18px; border-radius: 7px; font-size: 14px; min-height: 44px; }
        nav button[aria-pressed="true"] { color: #c93817; background: #fcf0eb; font-weight: 600; }
        nav .arrow { font-size: 26px; color: #d33e1b; padding: 5px 14px; }
        .note { font-size: 12px; color: #737379; line-height: 1.6; padding: 0 28px 22px; margin: 0; }
        .scroll-hint { display: none; }
        @container schema (max-width: 620px) {
          header { padding: 20px 18px 16px; } h2 { font-size: 20px; }
          .metrics { margin: 18px 16px 0; grid-template-columns: repeat(2, 1fr); }
          .metric:nth-child(2) { border-right: 0; } .metric:nth-child(-n+2) { border-bottom: 1px solid #e5e5e7; }
          .metric-value { font-size: 22px; } .metric { padding: 12px; }
          .note { padding: 0 18px 18px; }
          .scroll-hint { display: block; color: #777; font-size: 11px; padding: 12px 18px 0; }
          nav { gap: 2px; padding-left: 6px; padding-right: 6px; } nav button { padding: 10px; font-size: 12px; }
        }
        @media (prefers-reduced-motion: reduce) { .running { animation: none; } }
      </style>
      <ha-card>
        <header><div class="eyebrow">SOLVISLEO 180</div><h2>Anlagenschema · ${VIEWS[this._view]}</h2></header>
        ${this._view !== "heatpump" ? `<div class="metrics">${this._metrics()}</div>` : ""}
        <div class="scroll-hint">Schema seitlich verschieben ↔ · Werte für Details antippen</div>
        <div class="drawing" tabindex="0" role="region" aria-label="Anlagenschema, seitlich scrollbar">
          <svg viewBox="0 0 1100 555" xmlns="http://www.w3.org/2000/svg" role="group" aria-label="Anlagenschema ${VIEWS[this._view]}">
            ${this[this._view === "heating" ? "_heating" : this._view === "water" ? "_water" : "_heatpump"]()}
            ${this._tank()}
          </svg>
        </div>
        ${navigation ? `<nav aria-label="Anlagenschema wählen">
          <button class="arrow" data-view="${views[(index + 2) % 3]}" aria-label="Vorheriges Schema">‹</button>
          ${views.map((view) => `<button data-view="${view}" aria-pressed="${view === this._view}">${VIEWS[view]}</button>`).join("")}
          <button class="arrow" data-view="${views[(index + 1) % 3]}" aria-label="Nächstes Schema">›</button>
        </nav>` : ""}
        <p class="note">${this._hass?.connected === false ? "Verbindung zu Home Assistant unterbrochen. " : ""}Werte aus Home Assistant · Antippen öffnet den Verlauf.
          ${this._view === "heatpump" && unavailable.length ? `<br>Nicht verfügbar: ${escape(unavailable.join(", "))}.` : ""}
        </p>
      </ha-card>`;
    }
  }

  if (!customElements.get("solvis-schema-card")) {
    customElements.define("solvis-schema-card", SolvisSchemaCard);
    window.customCards = window.customCards || [];
    window.customCards.push({ type: "solvis-schema-card", name: "SolvisLeo Anlagenschema", description: "Heizung, Warmwasser und Wärmepumpe im Solvis-Portalstil", preview: false });
  }
})();
