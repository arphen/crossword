// The ONLY file that knows your selectors. Replace every value for your project.
export default {
  page: '/demo.html',
  rootSelector: '#root',
  attrs: { theme: 'data-theme', luma: 'data-luma', vibrance: 'data-vibrance' },
  lumas: ['standard', 'dim'],
  vibrances: ['vivid', 'soft', 'bold'],
  // Elements that carry --rank (identity is published, and shown on 2+ surfaces).
  rankWearers: ['.chip', '.lane > li', '.tile'],
  // Elements whose computed `color` IS the identity colour, and the attribute naming their pole.
  colorWearers: ['.chip'],
  poleAttr: 'data-lane',
  // Text that must stay legible (WCAG contrast ratio), measured on solid backgrounds.
  textPairs: [
    { text: 'li.is-selected > .chip', min: 4.5 },
    { text: '.tile', min: 4.5 },
  ],
  requiredTokens: ['--ramp-l', '--ramp-c', '--ember-alpha', '--flame-alpha', '--halo-alpha', '--ease-out'],
  // Must hold on the dim and veil tiers: bloom is gone.
  lowBloom: { '--ember-alpha': '0%' },
  maxGlass: 5,
  // Optional: runs after every page.goto (log in, seed data, pick a puzzle...).
  setup: async () => {},
};
