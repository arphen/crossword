// Mechanically ported from the curated Vue mobile behavior.
// Regenerate with node scripts/snapshot-react-behavior.mjs; original files remain unchanged.
export function createOptions({ axios, socket, ROOM_ID, INITIAL_ROLE, setTimeout, clearTimeout, setInterval, clearInterval, requestAnimationFrame, cancelAnimationFrame }) {
  return {
    el: '#app',
    delimiters: ['[[', ']]'],
    data: {
        role: INITIAL_ROLE,
        crossword: [],
        grid: {}, // Map "row,col" -> value
        activeEntry: null,
        activeCharIndex: 0,
        showSwapRequest: false,
        puzzleDate: null,
        isChecking: false,
        solvedKeys: [] // List of "clue_number-direction" for solved entries
    },
    computed: {
        myEntries() {
            if (!this.crossword) return [];
            return this.crossword.filter(e => e.direction === this.role);
        },
        sortedEntries() {
            return [...this.myEntries].sort((a, b) => {
                const aSolved = this.solvedKeys.includes(`${a.clue_number}-${a.direction}`);
                const bSolved = this.solvedKeys.includes(`${b.clue_number}-${b.direction}`);
                if (aSolved === bSolved) {
                    return a.clue_number - b.clue_number;
                }
                return aSolved ? 1 : -1;
            });
        },
        checkButtonLabel() {
            return this.isChecking ? "Clear Errors" : "Check";
        }
    },
    methods: {
        toggleCheck() {
            if (!this.isChecking) {
                // Enter check mode
                this.isChecking = true;
            } else {
                // Clear errors and exit check mode
                this.clearIncorrectAndMarkSolved();
                this.isChecking = false;
            }
        },
        clearIncorrectAndMarkSolved() {
            // First, identify fully correct entries BEFORE clearing anything
            // (Actually, we can just check if they are correct now)

            // 1. Mark solved entries
            this.myEntries.forEach(entry => {
                const key = `${entry.clue_number}-${entry.direction}`;
                if (this.solvedKeys.includes(key)) return; // Already solved

                const isPerfect = entry.characters.every((char, idx) => {
                    return this.isCellCorrect(entry, idx);
                });

                if (isPerfect) {
                    this.solvedKeys.push(key);
                }
            });

            // 2. Clear incorrect cells
            // We iterate over all entries to find incorrect cells.
            // Note: A cell might be part of two entries. If it's wrong in one, it's wrong in both.
            // We can just iterate over all myEntries and clear incorrect cells.
            this.myEntries.forEach(entry => {
                entry.characters.forEach((char, idx) => {
                    const val = this.getCellValue(entry, idx);
                    if (val && !this.isCellCorrect(entry, idx)) {
                        // It's incorrect, clear it
                        const { row, col } = this.getCoordinates(entry, idx);

                        // Only clear if it hasn't been cleared yet (to avoid double emit)
                        if (this.grid[`${row},${col}`]) {
                            this.$set(this.grid, `${row},${col}`, '');
                            socket.emit('update_cell', {
                                room: ROOM_ID,
                                row: row,
                                col: col,
                                value: ''
                            });
                        }
                    }
                });
            });
        },
        isEntryFilled(entry) {
            return entry.characters.every((char, idx) => {
                return !!this.getCellValue(entry, idx);
            });
        },
        isCellCorrect(entry, idx) {
            const val = this.getCellValue(entry, idx);
            if (!val) return false;
            const correctVal = entry.characters[idx].letters.toUpperCase();
            return val.toUpperCase() === correctVal;
        },
        async loadPuzzle(date) {
            try {
                const response = await axios.get(`/crossword_by_date/${date}`);
                this.crossword = response.data.entries;
            } catch (error) {
                console.error("Failed to load puzzle:", error);
                alert("Failed to load puzzle data.");
            }
        },
        getCellValue(entry, index) {
            const { row, col } = this.getCoordinates(entry, index);
            return this.grid[`${row},${col}`] || '';
        },
        getCoordinates(entry, index) {
            let row = entry.start_y;
            let col = entry.start_x;
            if (entry.direction === 'across') {
                col += index;
            } else {
                row += index;
            }
            return { row, col };
        },
        selectEntry(entry) {
            this.activeEntry = entry;
            this.activeCharIndex = 0;
            this.$nextTick(() => {
                if (this.$refs.hiddenInput && this.$refs.hiddenInput[0]) {
                    this.$refs.hiddenInput[0].focus();
                }
            });
        },
        focusInput(entry, index) {
            this.activeEntry = entry;
            this.activeCharIndex = index;
            this.$nextTick(() => {
                if (this.$refs.hiddenInput && this.$refs.hiddenInput[0]) {
                    this.$refs.hiddenInput[0].focus();
                }
            });
        },
        handleInput(e) {
            const val = e.target.value;
            if (!val) return;

            const char = val.slice(-1).toUpperCase();
            e.target.value = ''; // Clear input

            // Update local grid immediately for responsiveness
            const { row, col } = this.getCoordinates(this.activeEntry, this.activeCharIndex);
            this.$set(this.grid, `${row},${col}`, char);

            // Emit update
            socket.emit('update_cell', {
                room: ROOM_ID,
                row: row,
                col: col,
                value: char
            });

            // Move to next char
            if (this.activeCharIndex < this.activeEntry.characters.length - 1) {
                this.activeCharIndex++;
            }
        },
        handleKeydown(e) {
            if (e.key === 'Backspace') {
                const { row, col } = this.getCoordinates(this.activeEntry, this.activeCharIndex);

                // If current cell is empty, move back and delete
                if (!this.grid[`${row},${col}`] && this.activeCharIndex > 0) {
                    this.activeCharIndex--;
                    const prevCoords = this.getCoordinates(this.activeEntry, this.activeCharIndex);
                    this.$set(this.grid, `${prevCoords.row},${prevCoords.col}`, '');
                    socket.emit('update_cell', {
                        room: ROOM_ID,
                        row: prevCoords.row,
                        col: prevCoords.col,
                        value: ''
                    });
                } else {
                    // Just delete current
                    this.$set(this.grid, `${row},${col}`, '');
                    socket.emit('update_cell', {
                        room: ROOM_ID,
                        row: row,
                        col: col,
                        value: ''
                    });
                }
            }
        },
        requestSwap() {
            socket.emit('request_swap', { room: ROOM_ID });
            alert("Swap request sent!");
        },
        confirmSwap() {
            socket.emit('confirm_swap', { room: ROOM_ID });
            this.showSwapRequest = false;
            // Optimistic swap
            this.role = this.role === 'across' ? 'down' : 'across';
        }
    },
    mounted() {
        socket.emit('join', { room: ROOM_ID, role: this.role });

        socket.on('game_state', (data) => {
            this.grid = data.grid;
            if (!this.puzzleDate && data.puzzle_date) {
                this.puzzleDate = data.puzzle_date;
                this.loadPuzzle(this.puzzleDate);
            }
        });

        socket.on('cell_updated', (data) => {
            this.$set(this.grid, `${data.row},${data.col}`, data.value);
        });

        socket.on('swap_requested', () => {
            this.showSwapRequest = true;
        });

        socket.on('swap_confirmed', () => {
            this.role = this.role === 'across' ? 'down' : 'across';
            this.activeEntry = null; // Deselect to avoid confusion
        });
    }
};
}
