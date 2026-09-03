/**
 * Curated 15x15 topology template bank.
 *
 * Masks were produced by `scripts/design-topology-bank.mjs` (deterministic,
 * seeded search with mirror symmetry, minimum run length 3, checked cells,
 * connected white graph) and reviewed by hand. Every template must pass
 * `validateTopologyMask` — the bank test proves it for all entries.
 *
 * This is the curated bank from docs/plans/02 "Topology before fill": a
 * generated topology is a later, separately gated capability. Style labels
 * describe the intended day feel; day recipes select templates by measured
 * fill evidence, not by label alone.
 */

export type TopologyTemplate = Readonly<{
  id: string;
  style: 'wide-open' | 'stacked' | 'weave' | 'cornered' | 'dense' | 'human-derived';
  notes: string;
  mask: readonly string[];
}>;

const WIDTH = 15;

export const TEMPLATES: readonly TopologyTemplate[] = [
  {
    id: 'human-15x15',
    style: 'human-derived',
    notes:
      'Proven NYT-style human mask (the legacy app\'s reference grid). Fill-measured ' +
      'against the full lab lexicon: solved in ~2s at 79 search nodes, average answer ' +
      'length 4.8 — the calibration target every generated template must meet.',
    mask: [
      '....#....#.....',
      '....#....#.....',
      '....#....#.....',
      '...........#...',
      '####...#...#...',
      '......#......##',
      '.....#....#....',
      '.....#...#.....',
      '....#....#.....',
      '##......#......',
      '...#...#...####',
      '...#...........',
      '.....#....#....',
      '.....#....#....',
      '.....#....#....'
    ]
  },
  {
    id: 'wide-open-26',
    style: 'wide-open',
    notes:
      'Lightest block budget with three stacked 15-letter bands top and bottom. ' +
      'Long themed bands live naturally in the full-width rows; 39 snappy downs.',
    mask: [
      '...............',
      '...............',
      '...............',
      '....#######....',
      '.......#.......',
      '...............',
      '...............',
      '#####.....#####',
      '...............',
      '...............',
      '.......#.......',
      '....#######....',
      '...............',
      '...............',
      '...............'
    ]
  },
  {
    id: 'side-towers-31',
    style: 'stacked',
    notes:
      'Chunky corner stacks with an open center; balanced 4-7 letter downs and ' +
      'several 12-15 across lanes for theme material.',
    mask: [
      '.......#.......',
      '.......#.......',
      '...............',
      '####.......####',
      '...............',
      '....#.....#....',
      '...............',
      '##....###....##',
      '...............',
      '....#.....#....',
      '...............',
      '####.......####',
      '...............',
      '.......#.......',
      '.......#.......'
    ]
  },
  {
    id: 'double-stack-30',
    style: 'stacked',
    notes:
      'Two mirrored stacks of long downs flanking a wide middle band; classic ' +
      'wide-open Thursday/Friday feel.',
    mask: [
      '...............',
      '...............',
      '...............',
      '...#.......#...',
      '#####.....#####',
      '......###......',
      '...............',
      '...............',
      '...............',
      '......###......',
      '#####.....#####',
      '...#.......#...',
      '...............',
      '...............',
      '...............'
    ]
  },
  {
    id: 'pinwheel-33',
    style: 'weave',
    notes:
      'Interlocked 4/5/4 across rows with a barred center band; no full-width ' +
      'runs, so fill stays word-length nimble.',
    mask: [
      '....#.....#....',
      '....#.....#....',
      '...............',
      '##....###....##',
      '...............',
      '...#.......#...',
      '...............',
      '....#######....',
      '...............',
      '...#.......#...',
      '...............',
      '##....###....##',
      '...............',
      '....#.....#....',
      '....#.....#....'
    ]
  },
  {
    id: 'corner-notches-31',
    style: 'cornered',
    notes:
      'Deep corner anchors with a checkerboard center; longer downs than the ' +
      'wide-open styles, useful when themes lock the across lanes.',
    mask: [
      '##...........##',
      '...............',
      '...............',
      '...............',
      '.....#...#.....',
      '####.......####',
      '...............',
      '......###......',
      '...............',
      '####.......####',
      '.....#...#.....',
      '...............',
      '...............',
      '...............',
      '##...........##'
    ]
  },
  {
    id: 'three-bar-33',
    style: 'dense',
    notes:
      'Three horizontal block bars segment the grid into calm rooms; the most ' +
      'conservative fill surface in the bank.',
    mask: [
      '.....#...#.....',
      '.....#...#.....',
      '.....#...#.....',
      '##...........##',
      '#.............#',
      '...............',
      '...............',
      '...#########...',
      '...............',
      '...............',
      '#.............#',
      '##...........##',
      '.....#...#.....',
      '.....#...#.....',
      '.....#...#.....'
    ]
  },
  {
    id: 'stagger-32',
    style: 'weave',
    notes:
      'Staggered 2/4-block pairs down the flanks with a crossed middle; ' +
      'balanced across and down averages around six.',
    mask: [
      '...##.....##...',
      '....#.....#....',
      '....#.....#....',
      '...............',
      '......###......',
      '...............',
      '...............',
      '#####.....#####',
      '...............',
      '...............',
      '......###......',
      '...............',
      '....#.....#....',
      '....#.....#....',
      '...##.....##...'
    ]
  }
];

export function curatedTemplateBank(): readonly TopologyTemplate[] {
  return TEMPLATES;
}

export function templateById(id: string): TopologyTemplate | undefined {
  return TEMPLATES.find((template) => template.id === id);
}
