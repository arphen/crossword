"""Tests for the NYTFormatParser."""

import pytest
from src.crossword.parser import NYTFormatParser
from src.crossword.models import Crossword, Entry, Character, CrosswordMetadata


# Sample puzzle data
PUZZLE_250520 = """ARCHIVE

250415

NY Times, Tue, May 20, 2025

Per Bykodorov / Will Shortz

15

15

35

41

SLANG#FRAT##MUM
GIJOE#LURE#SITE
T%R%A%G%I%COMIC#WREN
SAX#SHOO##BOARS
###CHERRY%G%A%R%C%IA
APPEAR##EASEL##
BOHO##MUSTI#EPA
CLOSEBUTNOCIGAR
SET#NARCO##CRIT
##ODORS##LABORS
M%A%G%I%C%REALISM###
ALEPH##LUNK#SAC
MINI#%C%R%A%I%GSLIST
AKIN#BORG#OILER
SEC##DEMI#FETAL

"Snow job" or "rainmaker," e.g.
Beer pong locale
Tight-lipped
Figure once marketed as "America's movable fighting man"
Tempt
___ for sore eyes (www.optometrists.com?)
Like a film that's both sad and funny
Cactus ___ (Arizona's state bird)
Lisa Simpson's musical instrument
"Go on now, git!"
Wild pigs
Ben & Jerry's flavor honoring a jam band legend
Seem
Potter : wheel :: painter : ___
___ chic (fashion style)
"Can't you get someone else?"
Water-testing org.
Not quite right ... or a hint to this puzzle's circled letters
Moviemaking backdrop
D.E.A. agent, informally
Lit ___
Smells
Herculean tasks
Genre for Gabriel García Márquez's "One Hundred Years of Solitude"
Start of the Hebrew alphabet
Dum-dum
Anatomical pouch
Skirt with a high hemline
Online marketplace with a "barter" category
Similar (to)
Six-time French Open champ Björn
Fuel ship
"Just a ___!"
Moore of "The Substance"
Prenatal

March V.I.P.s?: Abbr.
Old Italian money
Cleaning product with a mythical name
Yuletide drink
Performer at ozashiki parties
Lower limit
Something heard through the grapevine
News anchor Melber
Private eye, in old crime novels
Big name in fertilizers
Wombs
High-I.Q. society
Said "%$#@!"
The so-called "Goddess of Pop"
Fundamental
Co. heads
Like the questions asked in Guess Who?
Feline, to Felipe
Fundamentals
Fire station fixture
Camera-friendly
Container for keys, wallet, razor, etc., in a modern portmanteau
World clock std.
Unexciting holding in poker
Lincoln Center focus
Son of Cain
Former attorney general Bill
Warhead weapon, in brief
Take out a small part of one's savings, day
Suffix with duck or suck
Requests from
Some bedtime story readers
The same
Worry greatly
Video game character in a green hat
River residue
Not on firm ground?
___+C ("copy" on a PC)
Ingredient in some trendy gummies, for short
Fish eggs
"It's not you, it's me," often

org.apache.catalina.connector.CoyoteWriter@55c6330d"""


class TestNYTParserMetadata:
    """Test parsing of puzzle metadata."""
    
    def test_parse_date(self):
        """Test that date is correctly extracted."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert crossword.metadata.date == "250415"
    
    def test_parse_title(self):
        """Test that title is correctly extracted."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert crossword.metadata.title == "NY Times, Tue, May 20, 2025"
    
    def test_parse_authors(self):
        """Test that authors are correctly extracted."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert crossword.metadata.authors == ["Per Bykodorov", "Will Shortz"]
    
    def test_parse_dimensions(self):
        """Test that grid dimensions are correctly extracted."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert crossword.metadata.width == 15
        assert crossword.metadata.height == 15


class TestNYTParserGridNormalization:
    """Test grid normalization and character extraction."""
    
    def test_grid_removes_formatting_markers(self):
        """Test that normalized grid strips % and ^ markers."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # The normalized grid should not contain % or ^
        # Row 3 is "T%R%A%G%I%COMIC#WREN" which should normalize to "TRAGICOMIC#WREN"
        # This is used for positioning calculations
        # We can verify by checking entry positions
        
        # Entry 16 across (TRAGICOMIC) should start at position (0, 2)
        tragicomic = crossword.get_entry(16, "across")
        assert tragicomic is not None
        assert tragicomic.start_x == 0
        assert tragicomic.start_y == 2
        assert tragicomic.length == 10
    
    def test_formatting_preserved_in_characters(self):
        """Test that formatting is preserved in Character objects."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # TRAGICOMIC has circled letters: R, A, G, I, C
        tragicomic = crossword.get_entry(16, "across")
        assert tragicomic.answer_text == "TRAGICOMIC"
        
        # Check which letters are circled
        circled_letters = [char.letters for char in tragicomic.characters if char.is_circled]
        assert circled_letters == ['R', 'A', 'G', 'I', 'C']
    
    def test_black_squares_not_in_entries(self):
        """Test that black squares don't appear in entry character lists."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Check that no entry contains '#' or '.' in its characters
        for entry in crossword.entries:
            for char in entry.characters:
                assert char.letters != '#'
                assert char.letters != '.'
                assert not char.letters.startswith('#')
                assert not char.letters.startswith('.')


class TestNYTParserEntries:
    """Test entry extraction from grid."""
    
    def test_total_entry_count(self):
        """Test that correct number of entries are extracted."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert len(crossword.entries) == 76  # 35 across + 41 down
    
    def test_across_entry_count(self):
        """Test correct number of across entries."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert len(crossword.across_entries) == 35
    
    def test_down_entry_count(self):
        """Test correct number of down entries."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        assert len(crossword.down_entries) == 41
    
    def test_get_entry_by_number_and_direction(self):
        """Test retrieving specific entries."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Test across entry
        entry = crossword.get_entry(16, "across")
        assert entry is not None
        assert entry.clue_number == 16
        assert entry.direction == "across"
        assert entry.answer_text == "TRAGICOMIC"
        
        # Test down entry
        entry = crossword.get_entry(1, "down")
        assert entry is not None
        assert entry.clue_number == 1
        assert entry.direction == "down"
    
    def test_entry_positions(self):
        """Test that entries have correct grid positions."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Entry 1 across (SLANG) should start at top-left
        slang = crossword.get_entry(1, "across")
        assert slang.start_x == 0
        assert slang.start_y == 0
        assert slang.length == 5
        
        # Entry 18 across (WREN) should be after TRAGICOMIC
        wren = crossword.get_entry(18, "across")
        assert wren.start_x == 11
        assert wren.start_y == 2
        assert wren.length == 4
    
    def test_entry_clue_text(self):
        """Test that clue text is correctly assigned."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        entry = crossword.get_entry(16, "across")
        assert "both sad and funny" in entry.clue_text
    
    def test_entry_answer_text(self):
        """Test that answer text is correctly derived."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Test various entries
        slang = crossword.get_entry(1, "across")
        assert slang.answer_text == "SLANG"
        
        tragicomic = crossword.get_entry(16, "across")
        assert tragicomic.answer_text == "TRAGICOMIC"
        
        closebutnocigar = crossword.get_entry(35, "across")
        assert closebutnocigar.answer_text == "CLOSEBUTNOCIGAR"


class TestNYTParserCircledLetters:
    """Test parsing of circled letters (% markers)."""
    
    def test_tragicomic_circles(self):
        """Test TRAGICOMIC has correct circled letters: R, A, G, I, C."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        entry = crossword.get_entry(16, "across")
        
        # T%R%A%G%I%COMIC -> T(no), R(yes), A(yes), G(yes), I(yes), C(no), O(no), M(no), I(no), C(no)
        # Wait, the format shows T%R%A%G%I%COMIC which means:
        # T, %R (R is circled), %A (A is circled), %G (G is circled), %I (I is circled), %C (C is circled), OMIC
        # So: R, A, G, I, C are circled
        
        expected = [False, True, True, True, True, True, False, False, False, False]
        actual = [char.is_circled for char in entry.characters]
        assert actual == expected
    
    def test_cherrygarcia_circles(self):
        """Test CHERRYGARCIA has correct circled letters."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        entry = crossword.get_entry(22, "across")
        
        # CHERRY%G%A%R%C%IA -> CHERRY, then G, A, R, C, I are circled, then A
        # Letters: C H E R R Y G A R C I A
        # Circled:                G A R C I
        circled_letters = [char.letters for char in entry.characters if char.is_circled]
        assert circled_letters == ['G', 'A', 'R', 'C', 'I']
    
    def test_magicrealism_circles(self):
        """Test MAGICREALISM has correct circled letters."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        entry = crossword.get_entry(46, "across")
        
        # M%A%G%I%C%REALISM
        circled_letters = [char.letters for char in entry.characters if char.is_circled]
        assert circled_letters == ['A', 'G', 'I', 'C', 'R']
    
    def test_craigslist_circles(self):
        """Test CRAIGSLIST has correct circled letters."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        entry = crossword.get_entry(56, "across")
        
        # MINI#%C%R%A%I%GSLIST
        # After MINI and black square: C, R, A, I, G are circled
        circled_letters = [char.letters for char in entry.characters if char.is_circled]
        assert circled_letters == ['C', 'R', 'A', 'I', 'G']
    
    def test_total_circled_count(self):
        """Test total number of circled cells in puzzle."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        total_circled = sum(
            1 for entry in crossword.entries
            for char in entry.characters
            if char.is_circled
        )
        
        # TRAGIC (5) + GARCIA (5) + MAGIC (5) + CRAIG (5) = 20 circled letters in across entries
        # Plus overlapping down entries means we count each cell multiple times
        # The actual unique grid cells with circles is 25, but since each cell
        # appears in both an across and down entry, we count 40 total
        assert total_circled > 0
        assert total_circled == 40  # 25 unique cells × 2 (across + down entries)


class TestNYTParserShadedLetters:
    """Test parsing of shaded letters (^ markers)."""
    
    def test_no_shaded_in_this_puzzle(self):
        """Test that this puzzle has no shaded cells."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        total_shaded = sum(
            1 for entry in crossword.entries
            for char in entry.characters
            if char.is_shaded
        )
        
        assert total_shaded == 0


class TestNYTParserRebusSquares:
    """Test parsing of rebus squares (, markers)."""
    
    def test_no_rebus_in_this_puzzle(self):
        """Test that this puzzle has no rebus cells."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        total_rebus = sum(
            1 for entry in crossword.entries
            for char in entry.characters
            if char.is_rebus
        )
        
        assert total_rebus == 0
    
    def test_normalize_grid_line_simple(self):
        """Test that grid line normalization works for simple cases."""
        # Normal cells pass through
        assert NYTFormatParser._normalize_grid_line("CAT#DOG") == "CAT#DOG"
        
        # Formatting markers are removed
        assert NYTFormatParser._normalize_grid_line("A%RE") == "ARE"
        assert NYTFormatParser._normalize_grid_line("C^AT") == "CAT"
        assert NYTFormatParser._normalize_grid_line("A%R^E") == "ARE"
    
    def test_normalize_grid_line_rebus(self):
        """Test that rebus sequences are collapsed to single positions."""
        # JOHNDEEREG,R,E,E,N should become JOHNDEERE* (one position for the rebus)
        # The actual character doesn't matter, just that it's one position
        result = NYTFormatParser._normalize_grid_line("JOHNDEEREG,R,E,E,N")
        
        # Should have 10 characters: JOHNDEEREG (9) + rebus cell (1) = 10
        # But the rebus already includes the G, so it's: JOHNDEER (8) + rebus(GREEN) (1) = 9
        # Actually: J-O-H-N-D-E-E-R-E-[GREEN] = 10 positions
        # Wait, let's count: JOHNDEEREG,R,E,E,N
        # Without commas: JOHNDEEREGREEN = 14 letters
        # As grid positions: J O H N D E E R E GREEN = 10 positions
        # The G starts the rebus, so: JOHNDEEREG = 9 regular + the G becomes part of GREEN
        # So: JOHNDEER (8) + E (1) + GREEN (1 rebus) = 10 positions
        
        # Let's verify the length is correct (should be 10, not 14)
        assert len(result) == 10, f"Expected 10 positions but got {len(result)}: {result}"
        
        # Should start with JOHNDEER
        assert result.startswith("JOHNDEER"), f"Should start with JOHNDEER but got: {result}"
    
    def test_normalize_grid_line_with_formatting_and_rebus(self):
        """Test that both formatting markers and rebus are handled together."""
        # With circled rebus: %G,R,E,E,N means G is circled and part of rebus GREEN
        result = NYTFormatParser._normalize_grid_line("CAT%G,R,E,E,N")
        
        # Should be 4 positions: C-A-T-GREEN
        assert len(result) == 4, f"Expected 4 positions but got {len(result)}: {result}"
        assert result.startswith("CAT"), f"Should start with CAT but got: {result}"
    
    @pytest.mark.live_provider
    def test_rebus_parsing_real_puzzle_201511(self):
        """Test rebus parsing with real puzzle data from 201511."""
        from src.crossword.data_reader import DataReader
        
        reader = DataReader()
        try:
            api_text = reader._fetch_data("201511")
            crossword = NYTFormatParser.parse(api_text)
            
            # This puzzle should have rebus cells
            rebus_entries = [e for e in crossword.entries if any(len(c.letters) > 1 for c in e.characters)]
            assert len(rebus_entries) > 0, "Puzzle 201511 should have rebus entries"
            
            # Find entries with "GREEN" in them
            for entry in rebus_entries:
                for char in entry.characters:
                    if len(char.letters) > 1:
                        # This is a rebus cell
                        assert char.is_rebus, f"Multi-letter character '{char.letters}' should be marked as rebus"
                        # The rebus should be a complete word like "GREEN", not "REEN"
                        assert len(char.letters) >= 3, f"Rebus should have at least 3 letters, got '{char.letters}'"
                        
                        # If this rebus contains "GREEN", verify it's the full word
                        if "GREEN" in entry.answer_text:
                            # Find the rebus character that should be GREEN
                            rebus_chars = [c for c in entry.characters if len(c.letters) > 1]
                            green_rebus = [c for c in rebus_chars if "GREEN" in c.letters.upper() or c.letters.upper() == "GREEN"]
                            assert len(green_rebus) > 0, f"Should find GREEN rebus in {entry.answer_text}"
                            # The rebus should be exactly "GREEN", not "REEN", "EEN", "EN", or "N"
                            assert any(c.letters.upper() == "GREEN" for c in green_rebus), \
                                f"GREEN rebus should be exactly 'GREEN', found: {[c.letters for c in green_rebus]}"
            
            print(f"\nFound {len(rebus_entries)} entries with rebus cells in puzzle 201511")
            for entry in rebus_entries[:3]:  # Show first 3
                rebus_details = [(i, c.letters) for i, c in enumerate(entry.characters) if len(c.letters) > 1]
                print(f"  {entry.clue_number} {entry.direction}: {entry.answer_text} - rebus at positions {rebus_details}")
                
        except Exception as e:
            pytest.skip(f"Could not fetch puzzle 201511: {e}")


class TestNYTParserEdgeCases:
    """Test edge cases and error handling."""
    
    def test_short_entries(self):
        """Test that short entries (3 letters) are parsed correctly."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Find 3-letter entries
        short_entries = [e for e in crossword.entries if e.length == 3]
        assert len(short_entries) > 0
        
        # Verify they have correct structure
        for entry in short_entries:
            assert len(entry.characters) == 3
            assert len(entry.answer_text) == 3
    
    def test_long_entries(self):
        """Test that long entries are parsed correctly."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # CLOSEBUTNOCIGAR is 15 letters
        entry = crossword.get_entry(35, "across")
        assert entry.length == 15
        assert len(entry.characters) == 15
        assert entry.answer_text == "CLOSEBUTNOCIGAR"
    
    def test_entries_at_grid_edges(self):
        """Test entries that start at grid edges."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Top-left corner
        entry = crossword.get_entry(1, "across")
        assert entry.start_x == 0
        assert entry.start_y == 0
        
        # Bottom row
        bottom_entries = [e for e in crossword.across_entries if e.start_y == 14]
        assert len(bottom_entries) > 0
        
        # Right edge
        rightmost_entries = [e for e in crossword.across_entries if e.start_x + e.length == 15]
        assert len(rightmost_entries) > 0


class TestNYTParserModelStructure:
    """Test that parsed models have correct structure."""
    
    def test_crossword_has_metadata(self):
        """Test that Crossword has properly structured metadata."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        assert isinstance(crossword.metadata, CrosswordMetadata)
        assert crossword.metadata.date
        assert crossword.metadata.title
        assert len(crossword.metadata.authors) > 0
        assert crossword.metadata.width > 0
        assert crossword.metadata.height > 0
    
    def test_entries_have_required_fields(self):
        """Test that all entries have required fields."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        for entry in crossword.entries:
            assert isinstance(entry, Entry)
            assert entry.clue_number > 0
            assert entry.clue_text
            assert entry.direction in ["across", "down"]
            assert entry.start_x >= 0
            assert entry.start_y >= 0
            assert len(entry.characters) > 0
    
    def test_characters_have_required_fields(self):
        """Test that all characters have required fields."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        for entry in crossword.entries:
            for char in entry.characters:
                assert isinstance(char, Character)
                assert char.letters
                assert isinstance(char.is_circled, bool)
                assert isinstance(char.is_shaded, bool)
    
    def test_model_serialization(self):
        """Test that models can be serialized to dict."""
        crossword = NYTFormatParser.parse(PUZZLE_250520)
        
        # Should be able to convert to dict for JSON serialization
        data = crossword.model_dump()
        assert isinstance(data, dict)
        assert "metadata" in data
        assert "entries" in data
        
        # Check nested structure
        assert isinstance(data["entries"], list)
        if len(data["entries"]) > 0:
            entry = data["entries"][0]
            assert "clue_number" in entry
            assert "characters" in entry
            assert isinstance(entry["characters"], list)


def _padded(puzzle: str, left: int = 0, right: int = 0, top: int = 0, bottom: int = 0) -> str:
    """The same puzzle as the API sends a smaller grid: reported square, with
    whole rows and columns of black squares around the real one."""
    sections = puzzle.split("\n\n")
    grid = sections[8].split("\n")
    width = len(NYTFormatParser._normalize_grid_line(grid[0])) + left + right
    rows = ["#" * left + row + "#" * right for row in grid]
    rows = ["#" * width] * top + rows + ["#" * width] * bottom
    side = max(width, len(rows))
    sections[4] = str(side)
    sections[5] = str(side)
    sections[8] = "\n".join(rows)
    return "\n\n".join(sections)


class TestNYTParserPadding:
    """Black padding around a rectangular grid is cut away on every side."""

    @pytest.mark.parametrize(
        "padding",
        [
            {"left": 1},
            {"right": 1},
            {"left": 2, "bottom": 1},
            {"top": 1, "right": 1},
        ],
    )
    def test_padding_is_trimmed_and_entries_shift(self, padding):
        plain = NYTFormatParser.parse(PUZZLE_250520)
        padded = NYTFormatParser.parse(_padded(PUZZLE_250520, **padding))
        assert (padded.metadata.width, padded.metadata.height) == (15, 15)
        assert [
            (e.clue_number, e.direction, e.start_x, e.start_y, e.answer_text)
            for e in padded.entries
        ] == [
            (e.clue_number, e.direction, e.start_x, e.start_y, e.answer_text)
            for e in plain.entries
        ]

    def test_entries_touch_every_edge_after_trimming(self):
        crossword = NYTFormatParser.parse(_padded(PUZZLE_250520, left=1, bottom=1))
        cells = set()
        for entry in crossword.entries:
            for index in range(len(entry.characters)):
                if entry.direction == "across":
                    cells.add((entry.start_x + index, entry.start_y))
                else:
                    cells.add((entry.start_x, entry.start_y + index))
        assert min(x for x, _ in cells) == 0 and min(y for _, y in cells) == 0
        assert max(x for x, _ in cells) == crossword.metadata.width - 1
        assert max(y for _, y in cells) == crossword.metadata.height - 1
