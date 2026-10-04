import React from 'react';
import Signifier from './Signifier';

const SIGNIFIER_KINDS = new Set([
  'thread',
  'stone',
  'cube',
  'key',
  'circle',
  'zero',
  'fork',
  'map',
  'dots',
  'seed',
  'shell',
  'orbit',
]);

const NUMERALS = {
  'numeral-zero': '0',
  'numeral-one': '1',
  'numeral-two': '2',
  'numeral-three': '3',
  'numeral-four': '4',
  'numeral-seven': '7',
  'numeral-eight': '8',
  'numeral-nine': '9',
  'numeral-clock-time': '03:17',
};

const MARKS = {
  'mark-question': '?',
  'mark-ampersand': '&',
  'mark-ellipsis': '…',
  'mark-colon': ':',
  'mark-slash': '/',
  'mark-pilcrow': '¶',
  'mark-therefore': '∴',
  'mark-tilde': '~',
};

function legacySignifierKind(item) {
  if (!Array.isArray(item.legacy_ids)) return null;
  return item.legacy_ids.find((legacyId) => SIGNIFIER_KINDS.has(legacyId)) || null;
}

function stableText(item) {
  if (item.kind === 'numeral') return NUMERALS[item.id] || item.id;
  if (item.kind === 'word') return item.id.replace(/^word-/, '');
  if (item.kind === 'typographic_mark') return MARKS[item.id] || item.id;
  return item.accessible_label || item.id;
}

function AbstractForm({ id }) {
  const drawings = {
    'form-offset-arcs': (
      <>
        <path d="M47 92a42 42 0 0 1 67-34" />
        <path d="M153 68a42 42 0 0 1-67 34" />
      </>
    ),
    'form-triangle-wire': <path d="m100 35 55 92H45Z" />,
    'form-square-grid': (
      <>
        <rect x="48" y="38" width="104" height="84" rx="1" />
        <path d="M82 38v84m35-84v84M48 66h104m-104 28h104" />
      </>
    ),
    'form-single-helix': (
      <>
        <path d="M62 35c76 20 0 70 76 90" />
        <path d="M138 35c-76 20 0 70-76 90" />
        <path d="M79 45h42m-34 20h26m-34 21h26m-34 20h42" />
      </>
    ),
    'form-wave-line': <path d="M35 81c17-49 34 49 51 0s34 49 51 0 34 49 51 0" />,
    'form-parallel-set': (
      <>
        <path d="M56 39v82m29-82v82m29-82v82m29-82v82" />
      </>
    ),
  };

  return (
    <svg
      className="future-stimulus-art__drawing"
      viewBox="0 0 200 160"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {drawings[id] || <circle cx="100" cy="80" r="4" />}
    </svg>
  );
}

function TextureMaterial({ id }) {
  const patterns = {
    'surface-cotton-weave': (
      <>
        <path d="M42 45h116M42 65h116M42 85h116M42 105h116M42 125h116" />
        <path d="M53 34v102m22-102v102m22-102v102m22-102v102m22-102v102" />
      </>
    ),
    'surface-brushed-metal': (
      <>
        <path d="M35 43h130m-120 12h109M35 67h130m-120 12h109M35 91h130m-120 12h109M35 115h130m-120 12h109" />
      </>
    ),
    'surface-corrugated-paper': (
      <>
        <path d="M39 42q10-13 20 0t20 0 20 0 20 0 20 0 20 0" />
        <path d="M39 60q10-13 20 0t20 0 20 0 20 0 20 0 20 0" />
        <path d="M39 78q10-13 20 0t20 0 20 0 20 0 20 0 20 0" />
        <path d="M39 96q10-13 20 0t20 0 20 0 20 0 20 0 20 0" />
        <path d="M39 114q10-13 20 0t20 0 20 0 20 0 20 0 20 0" />
      </>
    ),
    'surface-ceramic-glaze': (
      <>
        <path d="M51 44c-15 20 18 25 3 45s18 25 3 33m32-78c-15 20 18 25 3 45s18 25 3 33m32-78c-15 20 18 25 3 45s18 25 3 33" />
        <path d="M47 52c28 5 58-8 108 2" opacity=".45" />
      </>
    ),
    'surface-cork-grain': (
      <>
        <circle cx="59" cy="55" r="3" />
        <circle cx="104" cy="48" r="2" />
        <circle cx="139" cy="65" r="4" />
        <circle cx="79" cy="88" r="4" />
        <circle cx="122" cy="103" r="2" />
        <circle cx="52" cy="119" r="2" />
        <circle cx="151" cy="121" r="3" />
      </>
    ),
    'surface-ribbed-rubber': (
      <>
        <path d="M56 40 45 120m25-80-11 80m25-80-11 80m25-80-11 80m25-80-11 80m25-80-11 80m25-80-11 80" />
      </>
    ),
    'surface-wood-grain': (
      <>
        <path d="M40 53c25-19 45 18 68 0s37 6 53-5M40 76c26-16 42 16 70 0s36 10 51-3M40 102c26-17 47 17 71 0s31 8 50-3" />
        <ellipse cx="94" cy="78" rx="11" ry="7" />
      </>
    ),
    'surface-felt-fiber': (
      <>
        <path d="m51 47 42 64m-9-66 43 68m-68-39 80-19m-82 49 91-24m-62-34-4 78m34-80 10 74" />
      </>
    ),
  };

  return (
    <svg
      className="future-stimulus-art__texture"
      viewBox="0 0 200 160"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <rect x="31" y="27" width="138" height="106" rx="3" opacity=".12" />
      {patterns[id] || <path d="M42 80h116" />}
    </svg>
  );
}

/** Decorative, deterministic rendering for one versioned calibration stimulus. */
export default function StimulusArtwork({ item, presentationMode = 'visual' }) {
  if (!item || typeof item !== 'object') return null;

  const mode = ['visual', 'monochrome', 'text-equivalent'].includes(
    presentationMode,
  )
    ? presentationMode
    : 'visual';
  const signifierKind = legacySignifierKind(item);
  const className = [
    'future-stimulus-art',
    `future-stimulus-art--${item.kind || 'unknown'}`,
    `future-stimulus-art--${mode}`,
  ].join(' ');

  let artwork;
  if (mode === 'text-equivalent') {
    artwork = (
      <span className="future-stimulus-art__equivalent">
        {stableText(item)}
      </span>
    );
  } else if (signifierKind) {
    artwork = (
      <Signifier
        kind={signifierKind}
        className="future-stimulus-art__legacy"
      />
    );
  } else if (item.kind === 'color') {
    artwork = (
      <span
        className="future-stimulus-art__swatch"
        style={{ backgroundColor: item.swatch_hex || '#777777' }}
      />
    );
  } else if (item.kind === 'numeral' || item.kind === 'word') {
    artwork = (
      <span className="future-stimulus-art__type">
        {stableText(item)}
      </span>
    );
  } else if (item.kind === 'typographic_mark') {
    artwork = (
      <span className="future-stimulus-art__mark">
        {stableText(item)}
      </span>
    );
  } else if (item.kind === 'abstract_form') {
    artwork = <AbstractForm id={item.id} />;
  } else if (item.kind === 'texture_material') {
    artwork = <TextureMaterial id={item.id} />;
  } else {
    artwork = <span className="future-stimulus-art__type">{item.id}</span>;
  }

  return (
    <span
      className={className}
      data-stimulus-kind={item.kind}
      data-presentation-mode={mode}
      aria-hidden="true"
      style={mode === 'monochrome' ? { filter: 'grayscale(1)' } : undefined}
    >
      {artwork}
    </span>
  );
}
