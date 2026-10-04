// Presentation only: every representation of a crossing uses the active word's
// cell ordinal, including rebuses (one grid cell, regardless of letter count).
export function createSelectionPresentation(entry) {
    const cells = new Map();
    if (!entry) return cells;
    const length = entry.characters.length;
    entry.characters.forEach((_, index) => {
        const row = entry.start_y + (entry.direction === 'down' ? index : 0);
        const col = entry.start_x + (entry.direction === 'across' ? index : 0);
        const position = length > 1 ? index / (length - 1) : 0;
        cells.set(`${row},${col}`, {
            index,
            length,
            title: `Letter ${index + 1} of ${length} · ${entry.clue_number} ${entry.direction}`,
            style: { '--entry-position': `${Math.round(position * 1000) / 10}%` }
        });
    });
    return cells;
}
