// Mechanically ported from the curated Vue desktop behavior.
// Regenerate with node scripts/snapshot-react-behavior.mjs; original files remain unchanged.
export function createOptions({ axios, socket, ROOM_ID, INITIAL_ROLE, setTimeout, clearTimeout, setInterval, clearInterval, requestAnimationFrame, cancelAnimationFrame }) {
  return {
    delimiters: ['[[', ']]'],
    data() {
        // Check initial color scheme preference
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        // Set initial scheme if not already set (e.g., by server-side rendering or previous visit)
        if (!document.documentElement.style.getPropertyValue('color-scheme')) {
            document.documentElement.style.setProperty('color-scheme', prefersDark ? 'dark' : 'light');
        }

        return {
            crossword: [],
            grid: [],
            cellMap: new Map(),  // V2: Map of (x,y) -> cell object with formatting
            direction: 'across',
            isChecking: false,
            baseUrl: window.location.origin,
            completedWords: new Set(),  // Track completed words
            activeClueNumber: null,  // Track which clue is active for highlighting
            activeDirection: null,   // Track active clue's direction
            isOffline: false,
            cachedCrosswordsCount: {
                monday: 0,
                tuesday: 0,
                wednesday: 0,
                thursday: 0,
                friday: 0
            },
            solvedPuzzlesCount: {
                monday: 0,
                tuesday: 0,
                wednesday: 0,
                thursday: 0,
                friday: 0,
                saturday: 0,
                sunday: 0
            },
            activeCaching: {
                monday: false,
                tuesday: false,
                wednesday: false,
                thursday: false,
                friday: false
            },
            cachingErrors: {
                monday: 0,
                tuesday: 0,
                wednesday: 0,
                thursday: 0,
                friday: 0
            },
            isCachingInProgress: false,
            isDarkMode: document.documentElement.style.getPropertyValue('color-scheme') === 'dark',
            showSolvedModal: false, // For the solved puzzles modal
            showCacheModal: false, // For the cache status modal
            solvedPuzzlesList: {},   // To store { day: [id1, id2], ... }
            currentPuzzleMetadata: null, // To store metadata of the currently loaded puzzle
            score: 100, // Starting score
            timer: 0, // Time in seconds
            timerInterval: null, // Timer interval reference
            showFireworks: false, // Display fireworks overlay
            fireworks: [], // Array of active fireworks
            fireworksAnimationId: null, // Animation frame ID
            selectedWeekday: 'monday',
            lastLoadedWeekday: 'monday',
            checksUsed: 0, // Track number of times check_all was used
            revealsUsed: 0, // Track number of individual cells revealed
            showRebusMenu: false, // Show rebus context menu
            rebusInputValue: '', // Value in rebus input
            rebusMenuCell: { row: -1, col: -1 }, // Current rebus cell being edited
            rebusMenuPosition: { x: 0, y: 0 }, // Position of rebus menu

            // Multiplayer
            showMultiplayerModal: false,
            multiplayerRoomId: null,
            qrAcross: null,
            qrDown: null
        }
    },
    computed: {
        isHalfCompleted() {
            if (!this.crossword || this.crossword.length === 0) {
                return false;
            }
            return (this.completedWords.size / this.crossword.length) > 0.5;
        },
        weekdayOptions() {
            return [
                { value: 'monday', label: 'Monday' },
                { value: 'tuesday', label: 'Tuesday' },
                { value: 'wednesday', label: 'Wednesday' },
                { value: 'thursday', label: 'Thursday' },
                { value: 'friday', label: 'Friday' }
            ];
        }
    },
    watch: {
        selectedWeekday(newDay) {
            localStorage.setItem('selectedWeekday', newDay);
        },
        activeDirection(newDirection) {
            // Update body data attribute for CSS styling
            if (newDirection) {
                document.body.setAttribute('data-active-direction', newDirection);
            } else {
                document.body.removeAttribute('data-active-direction');
            }
        }
    },
    created() {
        // Load saved weekday
        this.selectedWeekday = localStorage.getItem('selectedWeekday') || 'monday';

        // Check online status
        window.addEventListener('online', this.handleOnlineStatus);
        window.addEventListener('offline', this.handleOnlineStatus);
        this.isOffline = !navigator.onLine;

        // Initialize cached counts
        this.updateCachedCounts();

        // Don't start aggressive caching on page load
        // It will only happen when:
        // 1. User comes online after being offline
        // 2. User loads a puzzle and cache is low (< 10 puzzles)

        this.loadCrossword(this.selectedWeekday);

        // Add click listener to close rebus menu when clicking outside
        document.addEventListener('click', this.handleDocumentClick);

        // Listen for multiplayer updates
        socket.on('cell_updated', (data) => {
            if (this.grid && this.grid[data.row] && typeof this.grid[data.row][data.col] !== 'undefined') {
                // Use Vue.set to ensure reactivity
                this.$set(this.grid[data.row], data.col, data.value);
            }
        });
    },
    beforeUnmount() {
        // Clean up timer when component is destroyed
        this.stopTimer();
        // Remove click listener
        document.removeEventListener('click', this.handleDocumentClick);
    },
    methods: {
        async checkAndStartCaching(force = false) {
            // Only cache if any day has fewer than 10 puzzles (low threshold)
            // Unless forced (manual trigger)
            const needsMore = Object.values(this.cachedCrosswordsCount).some(count => count < 10);
            if ((!needsMore && !force) || this.isCachingInProgress) return;

            // Check if caching ran recently (within last hour)
            // Skip this check if forced
            const lastCachingTime = localStorage.getItem('lastCachingTime');
            if (lastCachingTime && !force) {
                const timeSinceLastCaching = Date.now() - parseInt(lastCachingTime);
                const oneHour = 60 * 60 * 1000;
                if (timeSinceLastCaching < oneHour) {
                    console.log('Caching ran recently, skipping...');
                    return;
                }
            }

            this.isCachingInProgress = true;
            localStorage.setItem('lastCachingTime', Date.now().toString());

            try {
                await this.ensureCachesFilled();
            } finally {
                this.isCachingInProgress = false;
                // Reset all active flags to be sure
                Object.keys(this.activeCaching).forEach(day => {
                    this.activeCaching[day] = false;
                });
            }
        },
        handleOnlineStatus() {
            const wasOffline = this.isOffline;
            this.isOffline = !navigator.onLine;

            // If we just came online, check if we need more puzzles
            if (wasOffline && !this.isOffline) {
                this.checkAndStartCaching();
            }
        },
        updateCachedCounts() {
            const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];
            days.forEach(day => {
                const puzzles = JSON.parse(localStorage.getItem(`crosswords_${day}`) || '[]');
                this.cachedCrosswordsCount[day] = puzzles.length;
            });
        },
        updateSolvedCounts() {
            Object.keys(this.solvedPuzzlesCount).forEach(day => {
                const solved = JSON.parse(localStorage.getItem(`solved_${day}`) || '[]');
                this.solvedPuzzlesCount[day] = solved.length;
            });
        },
        isPuzzleSolved(day, puzzleId) {
            // puzzleId is expected to be metadata.date
            const solvedPuzzles = JSON.parse(localStorage.getItem(`solved_${day}`) || '[]');
            return solvedPuzzles.some(p => p.id === puzzleId);
        },
        async isPuzzleSolvedBackend(puzzleId) {
            // Check backend database for completion status
            try {
                const response = await axios.get(`${this.baseUrl}/api/completed_puzzles/${puzzleId}`);
                return response.data.completed === true;
            } catch (error) {
                console.error('Error checking backend for puzzle completion:', error);
                return false; // If backend unavailable, rely on localStorage
            }
        },
        async markPuzzleSolved(day, puzzleId) {
            // puzzleId is now the metadata.date from the current puzzle
            // We need this.currentPuzzleMetadata to get title and authors
            if (!this.currentPuzzleMetadata || this.currentPuzzleMetadata.date !== puzzleId) {
                console.error("Mismatch or missing metadata when marking puzzle solved.", puzzleId, this.currentPuzzleMetadata);
                return; // Safety check
            }

            const storageKey = `solved_${day}`;
            let solvedPuzzles = JSON.parse(localStorage.getItem(storageKey) || '[]');

            // Check if this puzzle ID already exists
            const existingEntry = solvedPuzzles.find(p => p.id === puzzleId);
            if (!existingEntry) {
                const solvedEntry = {
                    id: puzzleId, // Original puzzle date from NYT
                    title: this.currentPuzzleMetadata.title,
                    authors: this.currentPuzzleMetadata.authors,
                    dayOfWeekSolved: day, // The day category it was solved under (e.g., 'monday')
                    dateSolved: new Date().toISOString() // When the user solved it
                };
                solvedPuzzles.push(solvedEntry);
                localStorage.setItem(storageKey, JSON.stringify(solvedPuzzles));
                this.updateSolvedCounts(); // This might need adjustment if it just counts length
            }

            // Also save to backend database
            try {
                await axios.post(`${this.baseUrl}/api/completed_puzzles`, {
                    puzzle_date: puzzleId,
                    title: this.currentPuzzleMetadata.title,
                    authors: this.currentPuzzleMetadata.authors,
                    weekday: day,
                    time_taken: this.timer,
                    score: this.score
                });
                console.log('Puzzle completion saved to backend');
            } catch (error) {
                console.error('Error saving puzzle completion to backend:', error);
                // Don't fail if backend is unavailable - localStorage already has it
            }
        },
        getPuzzleId(puzzleMetadata) {
            // Use the unique date from metadata as the puzzle ID
            if (!puzzleMetadata || !puzzleMetadata.date) return null;
            return puzzleMetadata.date; // e.g., "231026"
        },
        isValidPuzzle(puzzleData) {
            // Validate that puzzle has required structure and data
            if (!puzzleData) {
                console.error('Puzzle data is null or undefined');
                return false;
            }

            // Check for metadata
            if (!puzzleData.metadata) {
                console.error('Puzzle is missing metadata');
                return false;
            }

            // Check for entries (the actual crossword data)
            if (!puzzleData.entries || !Array.isArray(puzzleData.entries)) {
                console.error('Puzzle is missing entries or entries is not an array');
                return false;
            }

            // Check that entries array is not empty
            if (puzzleData.entries.length === 0) {
                console.error('Puzzle has no entries (empty crossword)');
                return false;
            }

            // Validate that entries have required fields (new model)
            const hasValidEntries = puzzleData.entries.every(entry => {
                return entry.hasOwnProperty('clue_text') &&
                    entry.hasOwnProperty('clue_number') &&
                    entry.hasOwnProperty('characters') &&
                    entry.hasOwnProperty('start_x') &&
                    entry.hasOwnProperty('start_y') &&
                    entry.hasOwnProperty('direction') &&
                    Array.isArray(entry.characters) &&
                    entry.characters.length > 0 &&
                    entry.characters.every(char => char.hasOwnProperty('letters'));
            });

            if (!hasValidEntries) {
                console.error('Puzzle has invalid entries (missing required fields for new model)');
                return false;
            }

            return true;
        },
        async loadCrossword(day, attempt = 1) {
            day = day.toLowerCase();
            this.selectedWeekday = day;
            this.currentPuzzleMetadata = null; // Reset metadata on new load

            if (this.isOffline) {
                this.loadCachedCrossword(day);
                return;
            }

            // Safety check to prevent infinite recursion
            if (attempt > 10) {
                alert(`Could not find a valid unsolved ${day} puzzle after multiple attempts. Please try again later or choose a different day.`);
                return;
            }

            try {
                const response = await axios.get(`${this.baseUrl}/random_crossword/${day}`);
                // Response includes entries with characters array
                this.currentPuzzleMetadata = response.data.metadata;
                this.crossword = response.data.entries;

                // Validate puzzle data
                if (!this.isValidPuzzle(response.data)) {
                    console.error('Invalid puzzle received, trying another one...');
                    await this.loadCrossword(day, attempt + 1); // Try to get another one
                    return;
                }

                // Use the new metadata for puzzle ID generation
                const puzzleId = this.getPuzzleId(this.currentPuzzleMetadata);

                // Check both localStorage and backend for completion status
                if (puzzleId && (this.isPuzzleSolved(day, puzzleId) || await this.isPuzzleSolvedBackend(puzzleId))) {
                    console.log(`Already solved this puzzle (${puzzleId}), trying another one...`);
                    await this.loadCrossword(day, attempt + 1); // Try to get another one
                    return;
                }

                // Cache the whole puzzle object (metadata + entries)
                this.cacheCrossword(day, response.data);

                this.init();
                this.lastLoadedWeekday = day;
            } catch (error) {
                console.error(`Error loading ${day} crossword:`, error);
                // If fetch fails, try to load from cache
                this.loadCachedCrossword(day);
            }
        },
        cacheCrossword(day, puzzleData) {
            const storageKey = `crosswords_${day}`;
            let puzzles = JSON.parse(localStorage.getItem(storageKey) || '[]');

            // Don't cache invalid puzzles
            if (!this.isValidPuzzle(puzzleData)) {
                console.error('Attempting to cache invalid puzzle, skipping...');
                return;
            }

            const puzzleId = this.getPuzzleId(puzzleData.metadata);

            // Don't cache if we've already solved it
            if (puzzleId && this.isPuzzleSolved(day, puzzleId)) {
                return;
            }

            // Check if we already have this puzzle cached
            const isDuplicate = puzzles.some(p => this.getPuzzleId(p.metadata) === puzzleId);

            if (!isDuplicate) {
                // Add new puzzle and keep only the latest 50
                puzzles.push(puzzleData);
                if (puzzles.length > 50) {
                    puzzles = puzzles.slice(-50);
                }

                try {
                    localStorage.setItem(storageKey, JSON.stringify(puzzles));
                    this.updateCachedCounts();
                } catch (e) {
                    console.error('Error caching crossword:', e);
                    // If storage is full, remove the oldest puzzle and try again
                    if (e.name === 'QuotaExceededError') {
                        puzzles.shift();
                        localStorage.setItem(storageKey, JSON.stringify(puzzles));
                        this.updateCachedCounts();
                    }
                }
            }
        },
        loadCachedCrossword(day, attempt = 1) { // Add attempt counter for safety
            const storageKey = `crosswords_${day}`;
            let puzzles = JSON.parse(localStorage.getItem(storageKey) || '[]');

            if (puzzles.length === 0) {
                alert(`No cached ${day} crosswords available. Please connect to the internet to download new puzzles.`);
                return;
            }

            if (attempt > puzzles.length + 1 || attempt > 10) { // Safety break for recursion
                alert(`Could not find an unsolved ${day} crossword in the cache.`);
                return;
            }

            // Get a random puzzle index
            const randomIndex = Math.floor(Math.random() * puzzles.length);
            const selectedPuzzle = puzzles[randomIndex]; // This is the full {metadata, entries} object

            // Validate puzzle data
            if (!this.isValidPuzzle(selectedPuzzle)) {
                console.error(`Invalid puzzle in cache for ${day}. Removing and trying another.`);
                // Remove the invalid puzzle from the cached list
                puzzles.splice(randomIndex, 1);
                localStorage.setItem(storageKey, JSON.stringify(puzzles));
                this.updateCachedCounts();
                // Try loading another one from the cache
                this.loadCachedCrossword(day, attempt + 1);
                return;
            }

            // Use metadata for puzzle ID
            const puzzleId = this.getPuzzleId(selectedPuzzle.metadata);

            // Check if this puzzle is already solved
            if (puzzleId && this.isPuzzleSolved(day, puzzleId)) {
                console.log(`Cached puzzle (${puzzleId}) for ${day} is already solved. Removing and trying another.`);
                // Remove the solved puzzle from the cached list
                puzzles.splice(randomIndex, 1);
                localStorage.setItem(storageKey, JSON.stringify(puzzles));
                this.updateCachedCounts();

                // Try loading another one from the cache
                this.loadCachedCrossword(day, attempt + 1);
                return; // Stop execution for this attempt
            }

            // --- If puzzle is NOT solved, proceed as before ---
            this.currentPuzzleMetadata = selectedPuzzle.metadata; // Set metadata for the loaded puzzle
            this.crossword = selectedPuzzle.entries; // Set entries

            // Remove the used puzzle from cache
            puzzles.splice(randomIndex, 1);
            localStorage.setItem(storageKey, JSON.stringify(puzzles));
            this.updateCachedCounts();

            // If we're online and cache is getting low, fill it up
            if (!this.isOffline && puzzles.length < 25) {
                this.fillCache(day, 50 - puzzles.length);
            }

            this.init();
            this.lastLoadedWeekday = day;
        },
        handleWeekdayClick(day) {
            this.attemptLoadDay(day);
        },
        loadSelectedWeekday() {
            this.attemptLoadDay(this.selectedWeekday);
        },
        attemptLoadDay(day) {
            const normalizedDay = (day || '').toLowerCase();

            // Check if there's any progress in the current puzzle
            const hasProgress = this.grid.some(row =>
                row.some(cell => cell !== null && cell !== '')
            );

            if (hasProgress) {
                if (!confirm('Loading a new puzzle will erase your current progress. Are you sure you want to continue?')) {
                    return false; // User clicked Cancel, so don't load new puzzle
                }
            }

            this.isChecking = false;
            this.completedWords.clear(); // Clear completed words when loading new puzzle
            this.selectedWeekday = normalizedDay;
            this.loadCrossword(normalizedDay);
            return true;
        },
        init() {
            this.clearChecks(); // Reset visual indicators
            this.completedWords.clear(); // Clear completed words
            this.buildCellMap();  // Build cell map from crossword entries with new Character model
            this.calculateGridSize();
            this.generateGrid();  // Now creates full grid of black squares
            this.placeWords();    // Replaces black squares with actual cells
            this.startTimer();
            this.score = 100; // Reset score for new puzzle
            this.checksUsed = 0; // Reset checks counter
            this.revealsUsed = 0; // Reset reveals counter
        },
        buildCellMap() {
            // Build a map of (x,y) -> cell object from clean Character model
            this.cellMap.clear();

            this.crossword.forEach(entry => {
                // New model: entries have clue_number, start_x, start_y, characters array
                entry.characters.forEach((character, i) => {
                    const x = entry.direction === 'across' ? entry.start_x + i : entry.start_x;
                    const y = entry.direction === 'across' ? entry.start_y : entry.start_y + i;
                    const key = `${x},${y}`;

                    if (!this.cellMap.has(key)) {
                        // Create cell from Character model
                        // Character has: letters (string), is_circled (bool), is_shaded (bool)
                        // In the new model, rebus is detected by len(letters) > 1, not commas
                        this.cellMap.set(key, {
                            letters: character.letters,
                            is_circled: character.is_circled,
                            is_shaded: character.is_shaded,
                            is_rebus: character.letters.length > 1,  // Rebus if more than one letter
                            x, y,
                            userInput: '',
                            words: []
                        });
                    }

                    // Track which words use this cell
                    this.cellMap.get(key).words.push({
                        clue_number: entry.clue_number,
                        direction: entry.direction,
                        positionInWord: i
                    });
                });
            });
            console.log(`CellMap built with ${this.cellMap.size} cells`);
        },
        startTimer() {
            // Clear existing timer if any
            if (this.timerInterval) {
                clearInterval(this.timerInterval);
            }
            // Reset timer to 0
            this.timer = 0;
            // Start new timer
            this.timerInterval = setInterval(() => {
                this.timer++;
            }, 1000);
        },
        stopTimer() {
            if (this.timerInterval) {
                clearInterval(this.timerInterval);
                this.timerInterval = null;
            }
        },
        formatTime(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        },
        formatDate(dateStr) {
            // Convert YYMMDD to readable format
            if (!dateStr || dateStr.length !== 6) return '';
            const year = parseInt('20' + dateStr.substring(0, 2));
            const month = parseInt(dateStr.substring(2, 4)) - 1;
            const day = parseInt(dateStr.substring(4, 6));
            const date = new Date(year, month, day);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        },
        getCurrentDayName() {
            // Get the day name from the puzzle metadata date
            if (!this.currentPuzzleMetadata || !this.currentPuzzleMetadata.date) {
                return '';
            }
            const dateStr = this.currentPuzzleMetadata.date;
            const year = parseInt('20' + dateStr.substring(0, 2));
            const month = parseInt(dateStr.substring(2, 4)) - 1;
            const day = parseInt(dateStr.substring(4, 6));
            const date = new Date(year, month, day);
            const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
            return days[date.getDay()];
        },
        getXWordInfoLink() {
            // Convert YYMMDD to M/D/YYYY format for xwordinfo.com
            if (!this.currentPuzzleMetadata || !this.currentPuzzleMetadata.date) {
                return '#';
            }
            const dateStr = this.currentPuzzleMetadata.date;
            const year = parseInt('20' + dateStr.substring(0, 2));
            const month = parseInt(dateStr.substring(2, 4));
            const day = parseInt(dateStr.substring(4, 6));
            return `https://www.xwordinfo.com/Crossword?date=${month}/${day}/${year}`;
        },
        toggle_night_mode() {
            const currentScheme = document.documentElement.style.getPropertyValue('color-scheme');
            if (currentScheme.includes('dark')) {
                document.documentElement.style.setProperty('color-scheme', 'light');
                this.isDarkMode = false;
            } else {
                document.documentElement.style.setProperty('color-scheme', 'dark');
                this.isDarkMode = true;
            }
        },
        check_all() {
            if (this.isChecking) {
                this.clearChecks();
                return;
            }

            this.isChecking = true;
            this.checksUsed++; // Increment checks counter
            let allCorrect = true;
            let hasErrors = false; // Track if any incorrect letters found

            this.crossword.forEach(entry => {
                let isWordCorrect = true;  // Track if entire word is correct

                for (let i = 0; i < entry.characters.length; i++) {
                    const x = entry.direction === 'across' ? entry.start_x + i : entry.start_x;
                    const y = entry.direction === 'across' ? entry.start_y : entry.start_y + i;
                    const input = this.$refs[`input-${y}-${x}`]?.[0];
                    if (!input) continue;

                    const value = input.value.toLowerCase();
                    const correct = entry.characters[i].letters.toLowerCase();

                    if (value === '') {
                        input.classList.remove('red', 'green');
                        isWordCorrect = false;
                        allCorrect = false;
                    } else if (value === correct) {
                        input.classList.add('green');
                        input.classList.remove('red');
                    } else {
                        input.classList.add('red');
                        input.classList.remove('green');
                        isWordCorrect = false;
                        allCorrect = false;
                        hasErrors = true;
                    }
                }

                // If entry is completely correct, add it to completedWords
                if (isWordCorrect) {
                    this.completedWords.add(entry.clue_text);
                } else {
                    // If entry was previously marked as complete but is now incorrect, remove it
                    this.completedWords.delete(entry.clue_text);
                }
            });

            // Deduct points if there were errors (but keep score >= 0)
            if (hasErrors) {
                this.score = Math.max(0, this.score - 10);
            }

            // If all words are correct, mark the puzzle as solved
            if (allCorrect) {
                this.stopTimer(); // Stop the timer when puzzle is complete

                // Celebrate with fireworks and sounds!
                this.celebrateCompletion();

                const puzzleId = this.getPuzzleId(this.currentPuzzleMetadata);
                if (puzzleId) {
                    const day = this.getCurrentDay();
                    this.markPuzzleSolved(day, puzzleId);
                }
            }
        },
        getCurrentDay() {
            // Get the day of week from the puzzle metadata date
            if (!this.currentPuzzleMetadata || !this.currentPuzzleMetadata.date) {
                return 'monday';  // Fallback
            }

            // Parse date in YYMMDD format
            const dateStr = this.currentPuzzleMetadata.date;
            const year = parseInt('20' + dateStr.substring(0, 2));
            const month = parseInt(dateStr.substring(2, 4)) - 1;  // JS months are 0-indexed
            const day = parseInt(dateStr.substring(4, 6));

            const date = new Date(year, month, day);
            const dayOfWeek = date.getDay();  // 0 = Sunday, 1 = Monday, 2 = Tuesday, etc.

            const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
            return days[dayOfWeek];
        },
        find_index(rowIndex, cellIndex) {
            // Find the clue number for a cell if it's the start of an entry
            for (const entry of this.crossword) {
                if (entry.start_y === rowIndex && entry.start_x === cellIndex) {
                    return entry.clue_number;
                }
            }
            return null;
        },
        // V2: Cell helper methods
        getCell(x, y) {
            return this.cellMap.get(`${x},${y}`);
        },
        getCellClasses(rowIndex, cellIndex) {
            const cell = this.getCell(cellIndex, rowIndex);
            if (!cell) return 'black-cell';

            const classes = [];
            if (cell.is_shaded) classes.push('shaded');
            if (cell.is_circled) classes.push('circled');
            if (cell.is_rebus) classes.push('rebus');

            return classes.join(' ');
        },
        isRebus(x, y) {
            const cell = this.getCell(x, y);
            return cell && cell.is_rebus;
        },
        getRebusCount(x, y) {
            const cell = this.getCell(x, y);
            if (!cell || !cell.is_rebus) return '';
            // Return the number of letters in the rebus
            return cell.letters.length;
        },
        getEntryByClueNumber(clueNumber, direction) {
            // Find an entry by its clue number and direction
            return this.crossword.find(entry =>
                entry.clue_number === clueNumber && entry.direction === direction
            );
        },
        getCellsForEntry(entry) {
            // Get all (x, y) coordinates for cells in an entry
            if (!entry) return [];

            const cells = [];
            for (let i = 0; i < entry.characters.length; i++) {
                const x = entry.direction === 'across' ? entry.start_x + i : entry.start_x;
                const y = entry.direction === 'across' ? entry.start_y : entry.start_y + i;
                cells.push({ x, y });
            }
            return cells;
        },
        getIntersectingClues(clueNumber, direction) {
            // Find all clues in the opposite direction that intersect with this clue
            const entry = this.getEntryByClueNumber(clueNumber, direction);
            if (!entry) return [];

            const entryCells = this.getCellsForEntry(entry);
            const oppositeDirection = direction === 'across' ? 'down' : 'across';
            const intersectingClues = [];

            // For each cell in the entry, find which opposite-direction clues contain it
            entryCells.forEach(({ x, y }) => {
                this.crossword.forEach(otherEntry => {
                    if (otherEntry.direction === oppositeDirection) {
                        const otherCells = this.getCellsForEntry(otherEntry);
                        const hasIntersection = otherCells.some(cell => cell.x === x && cell.y === y);

                        if (hasIntersection && !intersectingClues.some(c =>
                            c.clue_number === otherEntry.clue_number && c.direction === otherEntry.direction
                        )) {
                            intersectingClues.push(otherEntry);
                        }
                    }
                });
            });

            return intersectingClues;
        },
        isCellInActiveEntry(rowIndex, cellIndex) {
            // Check if a cell is part of the currently active entry
            if (!this.activeClueNumber || !this.activeDirection) return false;

            const entry = this.getEntryByClueNumber(this.activeClueNumber, this.activeDirection);
            if (!entry) return false;

            const cells = this.getCellsForEntry(entry);
            return cells.some(cell => cell.x === cellIndex && cell.y === rowIndex);
        },
        isClueAffected(entry) {
            // Check if a clue intersects with the currently active clue
            if (!this.activeClueNumber || !this.activeDirection) return false;
            if (entry.direction === this.activeDirection) return false;

            const intersectingClues = this.getIntersectingClues(this.activeClueNumber, this.activeDirection);
            return intersectingClues.some(c =>
                c.clue_number === entry.clue_number && c.direction === entry.direction
            );
        },
        isActiveClue(entry) {
            // Check if this is the currently active clue
            return this.activeClueNumber === entry.clue_number &&
                this.activeDirection === entry.direction;
        },
        isCellInAffectedClue(entry, cellIndex) {
            // Check if a specific cell in an affected clue intersects with the active clue
            if (!this.activeClueNumber || !this.activeDirection) return false;
            if (entry.direction === this.activeDirection) return false;

            // Get the active entry
            const activeEntry = this.getEntryByClueNumber(this.activeClueNumber, this.activeDirection);
            if (!activeEntry) return false;

            // Get the position of this cell in the affected entry
            const x = entry.direction === 'across' ? entry.start_x + cellIndex : entry.start_x;
            const y = entry.direction === 'across' ? entry.start_y : entry.start_y + cellIndex;

            // Check if this position is in the active entry
            const activeCells = this.getCellsForEntry(activeEntry);
            return activeCells.some(cell => cell.x === x && cell.y === y);
        },
        calculateGridSize() {
            // Use metadata dimensions if available, otherwise calculate from entries
            if (this.currentPuzzleMetadata && this.currentPuzzleMetadata.width && this.currentPuzzleMetadata.height) {
                const width = this.currentPuzzleMetadata.width;
                const height = this.currentPuzzleMetadata.height;
                this.grid = Array(height).fill().map(() => Array(width).fill(null));  // null = black square
                console.log(`Grid size from metadata: ${width} x ${height}`);
            } else {
                // Fallback: Calculate grid dimensions from entries
                let maxX = 0;
                let maxY = 0;

                this.crossword.forEach(entry => {
                    const length = entry.characters.length;

                    if (entry.direction === 'across') {
                        maxX = Math.max(maxX, entry.start_x + length);
                        maxY = Math.max(maxY, entry.start_y + 1);
                    } else {
                        maxX = Math.max(maxX, entry.start_x + 1);
                        maxY = Math.max(maxY, entry.start_y + length);
                    }
                });

                this.grid = Array(maxY).fill().map(() => Array(maxX).fill(null));  // null = black square
                console.log(`Grid size calculated: ${maxX} x ${maxY}`);
            }
        },
        generateGrid() {
            // Grid is already initialized as full black squares (null values) in calculateGridSize
            // This method now just ensures the grid structure is ready
            console.log(`Grid initialized with ${this.grid.length} rows and ${this.grid[0]?.length || 0} columns`);
        },
        placeWords() {
            // Replace black squares with actual cells based on entries
            this.crossword.forEach(entry => {
                const wordLength = entry.characters.length;

                if (entry.direction === 'across') {
                    for (let i = 0; i < wordLength; i++) {
                        this.grid[entry.start_y][entry.start_x + i] = '';  // Empty string for user input
                    }
                } else {  // down
                    for (let i = 0; i < wordLength; i++) {
                        this.grid[entry.start_y + i][entry.start_x] = '';  // Empty string for user input
                    }
                }
            });
            console.log(`Placed ${this.crossword.length} entries in grid`);
        },
        handle_clue_click(event, entry) {
            // Set the direction to match the entry
            this.direction = entry.direction;

            // Set active clue for highlighting
            this.activeClueNumber = entry.clue_number;
            this.activeDirection = entry.direction;

            // Focus on the first cell of this entry
            this.$nextTick(() => {
                const input = this.$refs[`input-${entry.start_y}-${entry.start_x}`];
                if (input) {
                    input[0].focus();
                }
            });
        },
        handle_cell_click(event, entry, cellIndex) {
            // Stop event propagation so it doesn't trigger the clue wrapper click
            event.stopPropagation();

            // Set the direction to match the entry
            this.direction = entry.direction;

            // Calculate the actual cell position based on direction and index
            const x = entry.direction === 'across' ? entry.start_x + cellIndex : entry.start_x;
            const y = entry.direction === 'across' ? entry.start_y : entry.start_y + cellIndex;

            // Focus on the specific cell
            this.$nextTick(() => {
                const input = this.$refs[`input-${y}-${x}`];
                if (input) {
                    input[0].focus();
                }
            });
        },
        getCurrentAnswer(entry) {
            // Get current user input for an entry
            const answer = [];

            for (let i = 0; i < entry.characters.length; i++) {
                const x = entry.direction === 'across' ? entry.start_x + i : entry.start_x;
                const y = entry.direction === 'across' ? entry.start_y : entry.start_y + i;
                const value = this.grid[y]?.[x];
                answer.push((value === null || value === undefined || value === '') ? ' ' : value);
            }

            return answer;  // Array of characters
        },
        find_solution(rowIndex, cellIndex) {
            // Find the correct answer for a cell
            const cell = this.getCell(cellIndex, rowIndex);
            if (!cell) return null;

            // Return the letters from the Character model
            return cell.letters;
        },
        findCurrentWord(rowIndex, cellIndex) {
            // Find the entry that contains this cell in the current direction
            for (const entry of this.crossword) {
                if (entry.direction === this.direction) {
                    const length = entry.characters.length;
                    if (entry.direction === 'across') {
                        if (entry.start_y === rowIndex &&
                            cellIndex >= entry.start_x &&
                            cellIndex < entry.start_x + length) {
                            return entry;
                        }
                    } else {  // down
                        if (entry.start_x === cellIndex &&
                            rowIndex >= entry.start_y &&
                            rowIndex < entry.start_y + length) {
                            return entry;
                        }
                    }
                }
            }
            return null;
        },
        findNextWord(currentEntry) {
            if (!currentEntry) return null;

            // Sort entries by clue number for the current direction
            const directionEntries = this.crossword
                .filter(e => e.direction === currentEntry.direction)
                .sort((a, b) => a.clue_number - b.clue_number);

            // Find the next entry
            const currentIndex = directionEntries.findIndex(e => e.clue_number === currentEntry.clue_number);
            if (currentIndex < directionEntries.length - 1) {
                return directionEntries[currentIndex + 1];
            }
            return null;
        },
        isWordComplete(entry) {
            if (!entry) return false;
            const answer = this.getCurrentAnswer(entry).join('');
            // Word is complete if all cells have letters (no spaces)
            return answer.trim().length === entry.characters.length && !answer.includes(' ');
        },
        move(rowIndex, cellIndex, direction) {
            const sign = direction === 'forward' ? 1 : -1;
            const currentWord = this.findCurrentWord(rowIndex, cellIndex);

            // Check if we're at the end of a word or about to hit a black square
            if (currentWord && direction === 'forward') {
                const nextCell = this.direction === 'across' ?
                    this.grid[rowIndex]?.[cellIndex + 1] :
                    this.grid[rowIndex + 1]?.[cellIndex];

                const isLastCell = (this.direction === 'across' &&
                    cellIndex === currentWord.start_x + currentWord.characters.length - 1) ||
                    (this.direction === 'down' &&
                        rowIndex === currentWord.start_y + currentWord.characters.length - 1);

                const isBlackSquareNext = nextCell === null;

                if ((isLastCell || isBlackSquareNext) && this.isWordComplete(currentWord)) {
                    const nextWord = this.findNextWord(currentWord);
                    if (nextWord) {
                        this.$nextTick(() => {
                            const nextInput = this.$refs[`input-${nextWord.start_y}-${nextWord.start_x}`];
                            if (nextInput) {
                                nextInput[0].focus();
                                return;
                            }
                        });
                        return;
                    }
                }
            }

            // Check bounds
            if (this.direction === 'across' && (cellIndex + 1 * sign < 0 || cellIndex + 1 * sign >= this.grid[0].length)) {
                return;
            } else if (this.direction === 'down' && (rowIndex + 1 * sign < 0 || rowIndex + 1 * sign >= this.grid.length)) {
                return;
            }

            let targetX = cellIndex + sign * (this.direction === 'across');
            let targetY = rowIndex + sign * (this.direction === 'down');
            let targetCell = this.grid[targetY][targetX];

            // If target is a valid cell (not black square), move there
            if (targetCell !== null) {
                this.$nextTick(() => {
                    const nextInput = this.$refs[`input-${targetY}-${targetX}`];
                    if (nextInput) {
                        nextInput[0].focus();
                    }
                });
            } else {
                // Target is a black square, skip over it recursively
                this.move(targetY, targetX, direction);
            }
        },
        handle_crossword_cell_keydown(event, rowIndex, cellIndex) {
            // Check if this is a rebus cell and Space is pressed
            const isRebusCell = this.isRebus(cellIndex, rowIndex);
            if (isRebusCell && event.key === ' ') {
                event.preventDefault();
                this.openRebusMenu(event, rowIndex, cellIndex);
                return;
            }

            if (event.key === "ArrowRight") {
                if (this.direction === 'across')
                    this.move(rowIndex, cellIndex, 'forward');
                else
                    this.direction = 'across';
            } else if (event.key === "ArrowLeft") {
                if (this.direction === 'across')
                    this.move(rowIndex, cellIndex, 'backward');
                else
                    this.direction = 'across';
            } else if (event.key === "ArrowDown") {
                if (this.direction === 'down')
                    this.move(rowIndex, cellIndex, 'forward');
                else
                    this.direction = 'down';
            } else if (event.key === "ArrowUp") {
                if (this.direction === 'down')
                    this.move(rowIndex, cellIndex, 'backward');
                else
                    this.direction = 'down';
            } else if (event.key === "Backspace") {
                this.grid[rowIndex][cellIndex] = '';
                this.$forceUpdate();
                event.preventDefault();
                this.move(rowIndex, cellIndex, 'backward');
            } else if (event.key.length === 1 && /^[a-zA-Z]$/.test(event.key)) {
                // For rebus cells, only allow single-letter input via context menu
                if (isRebusCell) {
                    event.preventDefault();
                    this.openRebusMenu(event, rowIndex, cellIndex);
                    return;
                }
                this.grid[rowIndex][cellIndex] = event.key.toUpperCase();
                this.$forceUpdate();
                event.preventDefault();
                this.move(rowIndex, cellIndex, 'forward');
                if (this.isChecking) {
                    this.clearChecks();
                }
            }
        },
        handle_crossword_cell_contextmenu(event, rowIndex, cellIndex) {
            event.preventDefault(); // Prevent the default context menu from appearing

            // Check if this is a rebus cell
            const isRebusCell = this.isRebus(cellIndex, rowIndex);

            if (isRebusCell) {
                // Show rebus context menu
                this.openRebusMenu(event, rowIndex, cellIndex);
            } else {
                // Only reveal if the cell is empty
                const currentValue = this.grid[rowIndex][cellIndex];
                if (currentValue === '' || currentValue === null || currentValue === undefined) {
                    // Find the correct letter for this cell
                    const correctLetter = this.find_solution(rowIndex, cellIndex);
                    if (correctLetter) {
                        this.grid[rowIndex][cellIndex] = correctLetter.toUpperCase();
                        this.$forceUpdate();

                        // Increment reveals counter
                        this.revealsUsed++;

                        // Deduct points for revealing a letter (but keep score >= 0)
                        this.score = Math.max(0, this.score - 20);

                        // Clear any check marks if they're showing
                        if (this.isChecking) {
                            this.clearChecks();
                        }
                    }
                }
            }
        },
        openRebusMenu(event, rowIndex, cellIndex) {
            // Get current value or empty string
            const currentValue = this.grid[rowIndex][cellIndex] || '';
            this.rebusInputValue = currentValue;
            this.rebusMenuCell = { row: rowIndex, col: cellIndex };

            // Position the menu near the cell
            const cellElement = event.target.closest('.grid-cell');
            if (cellElement) {
                const rect = cellElement.getBoundingClientRect();
                this.rebusMenuPosition = {
                    x: rect.left + rect.width / 2,
                    y: rect.bottom + 10
                };
            } else {
                this.rebusMenuPosition = { x: event.clientX, y: event.clientY };
            }

            this.showRebusMenu = true;

            // Focus the input after menu is shown
            this.$nextTick(() => {
                const input = document.querySelector('.rebus-context-menu-input');
                if (input) {
                    input.focus();
                    input.select();
                }
            });
        },
        closeRebusMenu() {
            this.showRebusMenu = false;
            this.rebusInputValue = '';
            this.rebusMenuCell = { row: -1, col: -1 };
        },
        saveRebusValue() {
            if (this.rebusMenuCell.row >= 0 && this.rebusMenuCell.col >= 0) {
                const value = this.rebusInputValue.toUpperCase().trim();
                this.grid[this.rebusMenuCell.row][this.rebusMenuCell.col] = value;
                this.$forceUpdate();

                // Clear any check marks if they're showing
                if (this.isChecking) {
                    this.clearChecks();
                }
            }
            this.closeRebusMenu();
        },
        handleRebusMenuKeydown(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                this.saveRebusValue();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                this.closeRebusMenu();
            }
        },
        handleDocumentClick(event) {
            // Close rebus menu if clicking outside of it
            if (this.showRebusMenu) {
                const menu = document.querySelector('.rebus-context-menu');
                if (menu && !menu.contains(event.target)) {
                    this.closeRebusMenu();
                }
            }
        },
        clearChecks() {
            this.isChecking = false;
            document.querySelectorAll('.grid-cell input').forEach(input => {
                input.classList.remove('red', 'green');
            });
        },
        revealAll() {
            if (!confirm('Are you sure you want to reveal all answers? This will complete the puzzle but reduce your score.')) {
                return;
            }

            // Reveal all cells
            this.crossword.forEach(entry => {
                for (let i = 0; i < entry.characters.length; i++) {
                    const x = entry.direction === 'across' ? entry.start_x + i : entry.start_x;
                    const y = entry.direction === 'across' ? entry.start_y : entry.start_y + i;

                    // Only count as a reveal if the cell was empty
                    if (!this.grid[y][x] || this.grid[y][x] === '') {
                        this.revealsUsed++;
                    }

                    this.grid[y][x] = entry.characters[i].letters.toUpperCase();
                }
            });

            this.$forceUpdate();

            // Heavy score penalty for revealing all
            this.score = Math.max(0, this.score - 50);

            // Clear any check marks if they're showing
            if (this.isChecking) {
                this.clearChecks();
            }

            // Mark puzzle as complete
            this.stopTimer();
            const puzzleId = this.getPuzzleId(this.currentPuzzleMetadata);
            if (puzzleId) {
                const day = this.getCurrentDay();
                this.markPuzzleSolved(day, puzzleId);
            }
        },
        async fillCache(day, count) {
            // Don't start caching if we already have 50 puzzles
            const currentCount = this.cachedCrosswordsCount[day];
            if (currentCount >= 50 || this.activeCaching[day] || this.cachingErrors[day] > 3) {
                return;
            }

            this.activeCaching[day] = true;
            let successfulCaches = 0;

            try {
                for (let i = 0; i < count && this.cachedCrosswordsCount[day] < 50; i++) {
                    try {
                        const response = await axios.get(`${this.baseUrl}/random_crossword/${day}`);
                        await this.cacheCrossword(day, response.data);
                        successfulCaches++;
                        this.cachingErrors[day] = 0;
                        await new Promise(resolve => setTimeout(resolve, 100));
                    } catch (error) {
                        console.error(`Error caching ${day} crossword:`, error);
                        this.cachingErrors[day]++;
                        if (this.cachingErrors[day] > 3) break;
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                }
            } finally {
                this.activeCaching[day] = false;

                // Only retry if we need more and haven't hit error limit
                if (this.cachedCrosswordsCount[day] < 50 &&
                    successfulCaches > 0 &&
                    this.cachingErrors[day] <= 3 &&
                    !this.isOffline) {
                    setTimeout(() => this.checkAndStartCaching(), 5000);
                }
            }
        },
        async ensureCachesFilled() {
            const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];
            let needsCaching = false;

            // First check if any days need caching
            for (const day of days) {
                if (this.cachedCrosswordsCount[day] < 50 && this.cachingErrors[day] <= 3) {
                    needsCaching = true;
                    break;
                }
            }

            // If no days need caching, don't proceed
            if (!needsCaching) return;

            // Otherwise, start caching for days that need it
            for (const day of days) {
                if (this.cachedCrosswordsCount[day] < 50 && this.cachingErrors[day] <= 3) {
                    await this.fillCache(day, 50 - this.cachedCrosswordsCount[day]);
                }
            }
        },
        // New methods for solved puzzles modal
        async openSolvedModal() {
            await this.populateSolvedPuzzlesList();
            this.showSolvedModal = true;
        },
        closeSolvedModal() {
            this.showSolvedModal = false;
        },
        openCacheModal() {
            this.updateCachedCounts(); // Refresh counts before showing
            this.showCacheModal = true;
        },
        closeCacheModal() {
            this.showCacheModal = false;
        },
        async manuallyStartCaching() {
            if (this.isCachingInProgress) {
                alert('Caching is already in progress!');
                return;
            }

            // Clear the timestamp to allow immediate caching
            localStorage.removeItem('lastCachingTime');

            // Start caching
            await this.checkAndStartCaching(true);

            // Update the display
            this.updateCachedCounts();
        },
        async populateSolvedPuzzlesList() {
            const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
            const allSolved = {};

            // Initialize empty arrays for each day
            days.forEach(day => {
                allSolved[day] = [];
            });

            // Fetch from backend database
            try {
                const response = await axios.get(`${this.baseUrl}/api/completed_puzzles`);
                const backendPuzzles = response.data;

                // Group backend puzzles by weekday
                backendPuzzles.forEach(puzzle => {
                    const day = puzzle.weekday;
                    if (allSolved[day]) {
                        allSolved[day].push({
                            id: puzzle.puzzle_date,
                            title: puzzle.title,
                            authors: puzzle.authors,
                            dayOfWeekSolved: day,
                            dateSolved: puzzle.completed_at,
                            timeTaken: puzzle.time_taken,
                            score: puzzle.score
                        });
                    }
                });

                // Sort puzzles by completion date (most recent first)
                days.forEach(day => {
                    allSolved[day].sort((a, b) => new Date(b.dateSolved) - new Date(a.dateSolved));
                });

            } catch (error) {
                console.error('Error fetching completed puzzles from backend:', error);
                alert('Unable to load completed puzzles. Please make sure the server is running.');
            }

            this.solvedPuzzlesList = allSolved;
        },

        async markCurrentPuzzleAsComplete() {
            if (!this.currentPuzzleMetadata) {
                alert("No puzzle loaded to mark as complete.");
                return;
            }

            if (confirm("Are you sure you want to mark this puzzle as complete? You won't see it again.")) {
                const puzzleId = this.getPuzzleId(this.currentPuzzleMetadata);
                if (puzzleId) {
                    const day = this.getCurrentDay();
                    await this.markPuzzleSolved(day, puzzleId);
                    alert("Puzzle marked as complete. Loading a new one.");
                    this.loadCrossword(this.selectedWeekday);
                }
            }
        },

        // Multiplayer Methods
        openMultiplayerModal() {
            this.showMultiplayerModal = true;
        },
        closeMultiplayerModal() {
            this.showMultiplayerModal = false;
        },
        async startMultiplayerSession() {
            if (!this.currentPuzzleMetadata) return;
            try {
                const response = await axios.post('/api/multiplayer/create', {
                    date: this.currentPuzzleMetadata.date
                });
                this.multiplayerRoomId = response.data.room_id;

                // Get QRs
                const qr1 = await axios.get(`/api/multiplayer/qr/${this.multiplayerRoomId}/across`);
                this.qrAcross = qr1.data.qr_image;

                const qr2 = await axios.get(`/api/multiplayer/qr/${this.multiplayerRoomId}/down`);
                this.qrDown = qr2.data.qr_image;

                // Join room as spectator/host
                socket.emit('join', { room: this.multiplayerRoomId, role: 'host' });

            } catch (error) {
                console.error("Failed to start session:", error);
                alert("Failed to start multiplayer session.");
            }
        },
        async createHotspot() {
            try {
                await axios.post('/api/system/wifi');
            } catch (error) {
                alert("Failed to open system settings.");
            }
        },

        // Celebration and Fireworks Methods
        celebrateCompletion() {
            // Determine celebration level based on score
            let celebrationLevel = 'basic';
            let fireworkCount = 3;
            let soundCount = 1;

            if (this.score >= 90) {
                celebrationLevel = 'spectacular';
                fireworkCount = 20;
                soundCount = 5;
            } else if (this.score >= 70) {
                celebrationLevel = 'great';
                fireworkCount = 12;
                soundCount = 3;
            } else if (this.score >= 50) {
                celebrationLevel = 'good';
                fireworkCount = 7;
                soundCount = 2;
            }

            console.log(`Celebrating with ${celebrationLevel} level! Score: ${this.score}`);

            // Show fireworks
            this.showFireworks = true;
            this.launchFireworksSequence(fireworkCount);

            // Play sounds
            this.playCelebrationSounds(soundCount, celebrationLevel);

            // Auto-hide after celebration
            setTimeout(() => {
                this.stopFireworks();
            }, celebrationLevel === 'spectacular' ? 8000 : celebrationLevel === 'great' ? 6000 : 4000);
        },

        launchFireworksSequence(count) {
            const canvas = document.getElementById('fireworks-canvas');
            if (!canvas) return;

            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');

            this.fireworks = [];

            // Launch fireworks with delays
            for (let i = 0; i < count; i++) {
                setTimeout(() => {
                    this.launchFirework(canvas);
                }, i * (3000 / count)); // Spread launches over 3 seconds
            }

            // Start animation loop
            this.animateFireworks(canvas, ctx);
        },

        launchFirework(canvas) {
            const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#ff8800', '#ff0088'];
            const firework = {
                x: Math.random() * canvas.width,
                y: canvas.height,
                targetY: Math.random() * canvas.height * 0.5 + 50,
                color: colors[Math.floor(Math.random() * colors.length)],
                phase: 'launch',
                particles: []
            };
            this.fireworks.push(firework);
        },

        animateFireworks(canvas, ctx) {
            if (!this.showFireworks) return;

            ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            this.fireworks = this.fireworks.filter(firework => {
                if (firework.phase === 'launch') {
                    // Launch phase - rocket going up
                    firework.y -= 5;
                    ctx.fillStyle = firework.color;
                    ctx.beginPath();
                    ctx.arc(firework.x, firework.y, 3, 0, Math.PI * 2);
                    ctx.fill();

                    // Check if reached target
                    if (firework.y <= firework.targetY) {
                        firework.phase = 'explode';
                        this.createExplosion(firework);
                    }
                    return true;
                } else if (firework.phase === 'explode') {
                    // Explosion phase
                    let aliveParticles = 0;
                    firework.particles.forEach(particle => {
                        if (particle.life > 0) {
                            particle.x += particle.vx;
                            particle.y += particle.vy;
                            particle.vy += 0.1; // Gravity
                            particle.life -= 1;

                            ctx.fillStyle = `rgba(${particle.r}, ${particle.g}, ${particle.b}, ${particle.life / 100})`;
                            ctx.beginPath();
                            ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                            ctx.fill();

                            aliveParticles++;
                        }
                    });
                    return aliveParticles > 0;
                }
                return false;
            });

            this.fireworksAnimationId = requestAnimationFrame(() => this.animateFireworks(canvas, ctx));
        },

        createExplosion(firework) {
            const particleCount = 50 + Math.random() * 50;
            const color = this.hexToRgb(firework.color);

            for (let i = 0; i < particleCount; i++) {
                const angle = (Math.PI * 2 * i) / particleCount;
                const velocity = 2 + Math.random() * 3;

                firework.particles.push({
                    x: firework.x,
                    y: firework.y,
                    vx: Math.cos(angle) * velocity,
                    vy: Math.sin(angle) * velocity,
                    r: color.r,
                    g: color.g,
                    b: color.b,
                    life: 100,
                    size: 2 + Math.random() * 2
                });
            }
        },

        hexToRgb(hex) {
            const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
            return result ? {
                r: parseInt(result[1], 16),
                g: parseInt(result[2], 16),
                b: parseInt(result[3], 16)
            } : { r: 255, g: 255, b: 255 };
        },

        stopFireworks() {
            this.showFireworks = false;
            this.fireworks = [];
            if (this.fireworksAnimationId) {
                cancelAnimationFrame(this.fireworksAnimationId);
                this.fireworksAnimationId = null;
            }
        },

        playCelebrationSounds(count, level) {
            // Create AudioContext for sound generation
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;

            const audioContext = new AudioContext();

            // Play multiple ascending tones
            for (let i = 0; i < count; i++) {
                setTimeout(() => {
                    this.playVictoryTone(audioContext, i, level);
                }, i * 300);
            }

            // Grand finale sound for spectacular
            if (level === 'spectacular') {
                setTimeout(() => {
                    this.playGrandFinale(audioContext);
                }, count * 300 + 200);
            }
        },

        playVictoryTone(audioContext, index, level) {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            // Ascending scale frequencies
            const frequencies = [523.25, 587.33, 659.25, 783.99, 880.00, 987.77, 1046.50];
            oscillator.frequency.value = frequencies[index % frequencies.length];
            oscillator.type = level === 'spectacular' ? 'sine' : 'triangle';

            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        },

        playGrandFinale(audioContext) {
            // Play a triumphant chord
            const frequencies = [523.25, 659.25, 783.99]; // C major chord

            frequencies.forEach((freq, i) => {
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();

                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);

                oscillator.frequency.value = freq;
                oscillator.type = 'sine';

                gainNode.gain.setValueAtTime(0.2, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 1.5);

                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 1.5);
            });
        }
    }
};
}
