import React from 'react';
import {
  GROUPING_MODES,
  GLYPH_LEVELS,
  LUMA_LEVELS,
  SCALE_LEVELS,
  VIBRANCE_LEVELS,
  VIEW_DEFAULTS,
} from './viewSettings.js';

// A native details/summary keeps the cluster keyboard- and screen-reader-correct
// for free; the tiers are just progressive disclosure of the same settings
// object, so a reader can stop at mini and never see the rest.
const TIERS = [
  {
    key: 'mini',
    title: 'Mini',
    hint: 'Comfort',
    rows: [
      {
        key: 'luma',
        label: 'Brightness',
        options: LUMA_LEVELS,
        labels: { standard: 'Standard', dim: 'Dim', veil: 'Veil' },
      },
      {
        key: 'scale',
        label: 'Board size',
        options: SCALE_LEVELS,
        labels: { compact: 'S', normal: 'M', full: 'L' },
      },
    ],
  },
  {
    key: 'micro',
    title: 'Micro',
    hint: 'Reading aids',
    rows: [
      {
        key: 'ramp',
        label: 'Number colours',
        options: [false, true],
        labels: { false: 'Off', true: 'On' },
      },
      {
        key: 'vibrance',
        label: 'Colour intensity',
        options: VIBRANCE_LEVELS,
        labels: { soft: 'Soft', vivid: 'Vivid', bold: 'Bold' },
      },
      {
        key: 'grouping',
        label: 'Letter track',
        options: GROUPING_MODES,
        labels: { auto: 'Words', five: '5s', none: 'Solid' },
      },
      {
        key: 'rail',
        label: 'Clue rail',
        options: [false, true],
        labels: { false: 'Off', true: 'On' },
      },
    ],
  },
  {
    key: 'nano',
    title: 'Nano',
    hint: 'Board cues',
    rows: [
      {
        key: 'cues',
        label: 'Square notches',
        options: [false, true],
        labels: { false: 'Off', true: 'On' },
      },
      {
        key: 'glyph',
        label: 'Letter weight',
        options: GLYPH_LEVELS,
        labels: { regular: 'Regular', firm: 'Firm' },
      },
    ],
  },
];

// Every row's labels are keyed by the option's own value, so a boolean toggle is
// looked up as "true"/"false" - the same string the button's key uses.
const optionValue = (value) => String(value);

export default function ViewControls({ settings, onChange, onReset }) {
  const choose = (key, value) => onChange({ ...settings, [key]: value });

  return (
    <details className="view-cluster" data-testid="view-cluster">
      <summary
        className="view-cluster-summary"
        title="Adjust how the board reads"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          aria-hidden="true"
          focusable="false"
        >
          <line x1="4" y1="21" x2="4" y2="14"></line>
          <line x1="4" y1="10" x2="4" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12" y2="3"></line>
          <line x1="20" y1="21" x2="20" y2="16"></line>
          <line x1="20" y1="12" x2="20" y2="3"></line>
          <line x1="1" y1="14" x2="7" y2="14"></line>
          <line x1="9" y1="8" x2="15" y2="8"></line>
          <line x1="17" y1="16" x2="23" y2="16"></line>
        </svg>
        <span>View</span>
      </summary>
      <div className="view-cluster-panel">
        {TIERS.map((tier) => (
          <fieldset key={tier.key} className="view-tier" data-tier={tier.key}>
            <legend>
              <span className="view-tier-title">{tier.title}</span>
              <span className="view-tier-hint">{tier.hint}</span>
            </legend>
            {tier.rows.map((row) => (
              <div key={row.key} className="view-row">
                <span className="view-row-label">{row.label}</span>
                <span
                  className="view-choices"
                  role="group"
                  aria-label={row.label}
                >
                  {row.options.map((option) => {
                    const selected = settings[row.key] === option;
                    return (
                      <button
                        key={optionValue(option)}
                        type="button"
                        className="view-choice"
                        aria-pressed={selected}
                        onClick={() => choose(row.key, option)}
                      >
                        {row.labels[optionValue(option)]}
                      </button>
                    );
                  })}
                </span>
              </div>
            ))}
          </fieldset>
        ))}
        <button type="button" className="view-reset" onClick={onReset}>
          Reset to defaults ({VIEW_DEFAULTS.luma})
        </button>
      </div>
    </details>
  );
}
