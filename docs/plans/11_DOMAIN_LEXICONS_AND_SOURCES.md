# Domain lexicons: acquiring material with ways into it

Concept note and source orientation, 27 September 2026. Part of the [conceptual correspondence](README.md#conceptual-correspondence). Sources below were checked for this note; no datasets were downloaded or integrated.

You do need more wordlists. But the valuable acquisition is not simply more admissible strings. It is a set of names, concepts, expressions, and reliable relations from which the constructor can offer different kinds of access.

A domain list answers “what could appear?” A fact collection answers “what can truthfully be said about it?” An association resource answers “what might this bring to mind?” A frequency resource approximates how often a form appears in particular language data. None substitutes for the others. In particular, association is not sufficient justification for a clue answer.

## What a physics pack should contain

A useful pack would mix recognizable people; substantive concepts; instruments and practices; established multiword expressions; and ordinary words with technical lives. BOHR, ENTROPY, INTERFEROMETER, and FIELD contribute different pleasures. A set of surnames alone would personalize the roll call while leaving much of the discipline's imagination unused.

There is also a useful distinction between a complete directory and a playable selection. A directory aims to include everyone who qualifies. A crossword selection asks which entries reward recognition, admit interesting clues, or become meaningful discoveries. Fame, curriculum presence, everyday overlap, and the user's own expertise are different reasons to include an entry.

For every candidate, the conceptual questions are simple: which entity or sense is intended; which written forms are legitimate; who might recognize it; and what worthwhile clue routes exist? The solver may ultimately need a scored string, but that string should be a projection of richer material.

## Concrete sources worth knowing

| Resource | What it contributes | How to obtain or consult it | Main limitation for this project |
| --- | --- | --- | --- |
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Data_access) | Structured entities and relations from which to build subject selections | Narrow queries through its query service, entity JSON for selected records, dumps for bulk work | Membership and completeness need inspection; a large result set is not an editorial selection |
| [Open English Wordnet, including 2025+](https://en-word.net/downloads/) | Lexical senses and relations; the plus edition adds curated proper names | Official downloadable JSON, XML, and other formats | Neither edition is a complete disciplinary canon or a ready-made crossword list |
| [CERN physics material](https://home.cern/science/physics/) and [MacTutor](https://mathshistory.st-andrews.ac.uk/) | Specialist reference material for physics and mathematical biographies | Consult the relevant articles and indexes when establishing a domain's useful concepts and people | Reference access does not establish a license to redistribute a bulk derivative corpus |
| [wordfreq](https://github.com/rspeer/wordfreq) | Estimates of word frequency across languages | Its documented library interface | Frequency is not personal familiarity, phrase quality, or factual grounding |
| [Small World of Words](https://smallworldofwords.org/en/project/research) | Human word-association data, unusually relevant to the signifying-chain idea | Official research releases; exploratory views are separate snapshots | Population associations are not individual associations; the research page lists restrictive reuse terms |

Wikidata's structured data are available under CC0. It is the strongest starting candidate here for assembling cross-domain entity selections, with identity and relationships retained. That recommendation is editorial judgment, not a claim that its coverage is unbiased or that every statement is verified. Its documentation distinguishes bounded queries from bulk access and provides concrete access methods. [Data access](https://www.wikidata.org/wiki/Wikidata:Data_access), [copyright scope](https://www.wikidata.org/wiki/Wikidata:Copyright).

There is a particularly relevant detail in the existing project: [the lexicon notes](../../tools/lexicon/README.md) describe staging the base OEWN 2025 edition. The official download page says that edition moved proper nouns into Open English Namenet, while 2025+ includes a curated selection of them. The plus JSON archive is therefore a concrete additional candidate, not something the existing importer has already supplied. OEWN is released under CC BY 4.0. [Official editions and downloads](https://en-word.net/downloads/).

For wordfreq, keep the distinction between software and data terms: its README documents MIT-licensed code, CC BY-SA data, additional attribution, and its intended library use. Treat it as a scoring aid rather than assuming its contents can be exported into an unattributed flat list. [Project documentation](https://github.com/rspeer/wordfreq).

Small World of Words is almost exactly the empirical counterpart to one strand of your idea: it collects what people associate with cues. But the checked research page lists CC BY-NC-ND 3.0. It belongs on the research shortlist; those terms do not justify assuming commercial adaptation is permitted. Even with suitable permission, its associations would suggest candidate paths, not certify meanings or describe an individual. [Research releases and terms](https://smallworldofwords.org/en/project/research).

## Preserve multiple identities behind one spelling

Names require more care than uppercasing. A surname is not an entity identifier; a full name, short name, transliteration, and ordinary word can lead to different interpretations. A solver may collapse them into the same grid string while the clue writer must keep them distinct. First names should not be extracted mechanically from every international naming convention.

The same applies to spaces and diacritics. Their removal can be appropriate for a declared grid convention, but the original form should survive so that the clue and any explanation can use it correctly. Established phrases deserve explicit preservation: throwing away every multiword item would discard much of the long-answer experience you want.

## Abundance can make the fill worse

A larger dictionary gives a constraint solver more escapes. Some escapes are excellent; others are awkward abbreviations, obscure names, or strings that technically exist but offer little pleasure. Expanded domain coverage therefore changes the editorial selection problem as much as the construction problem.

I would judge a new pack by the new experiences it enables: a real foothold for a knowledgeable player, an unfamiliar entry that becomes learnable, an ordinary word acquiring another life, a satisfying long expression. Raw entry count measures none of those reliably.

The strategic asset is the curated relation between an answer, its possible clues, and the audiences for whom those clues work. Public sources supply much of the material. Your editorial decisions make it a crossword vocabulary.
