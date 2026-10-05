import { TIERS, readViewSettings, writeViewSettings, applyViewSettings, VIEW_DEFAULTS } from './view-settings.js';

export function mountViewPanel(root, host) {
  let settings = readViewSettings();
  applyViewSettings(root, settings);
  host.innerHTML = `
    <details class="view-cluster"><summary class="view-cluster-summary" title="Adjust how this reads">View</summary>
      <div class="view-cluster-panel">${TIERS.map((t) => `
        <fieldset class="view-tier" data-tier="${t.key}">
          <legend><span>${t.title}</span><span class="view-tier-hint">${t.hint}</span></legend>
          ${t.rows.map((r) => `
            <div class="view-row"><span class="view-row-label">${r.label}</span>
              <span class="view-choices" role="group" aria-label="${r.label}">
                ${r.options.map((o) => `<button type="button" class="view-choice" data-key="${r.key}" data-value="${o}" aria-pressed="${settings[r.key] === o}">${typeof o === 'boolean' ? (o ? 'On' : 'Off') : o}</button>`).join('')}
              </span></div>`).join('')}
        </fieldset>`).join('')}
        <button type="button" class="view-reset">Reset to defaults</button>
      </div>
    </details>`;
  const sync = () => { applyViewSettings(root, settings); writeViewSettings(settings);
    host.querySelectorAll('.view-choice').forEach((b) => b.setAttribute('aria-pressed', String(String(settings[b.dataset.key]) === b.dataset.value))); };
  host.addEventListener('click', (e) => {
    const b = e.target.closest('.view-choice'); const r = e.target.closest('.view-reset');
    if (b) { const cur = settings[b.dataset.key]; settings = { ...settings, [b.dataset.key]: typeof cur === 'boolean' ? b.dataset.value === 'true' : b.dataset.value }; sync(); }
    if (r) { settings = { ...VIEW_DEFAULTS }; sync(); }
  });
}
