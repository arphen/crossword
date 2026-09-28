# Lexicon sources and staged imports

`source-ledger.json` is the machine-readable record for lexicon inputs. Its
`sources` still describe the 78-answer local lexicon and its unresolved
`NOASSERTION` source; the separate `stagedImports` collection records Open
English Wordnet (OEWN) 2025 without implying it contributed to that older
artifact. The overall legacy artifact remains `owner-review-required`: a
license grant does not provide editorial/factual review, and the OEWN staging
artifact is never admitted automatically.

## OEWN 2025 offline importer

`oewn_import.py` imports the official `english-wordnet-2025-json.zip` without
network access. It requires the exact archive SHA-256
`7d749f6e2c39e6970e4997839dcf6e42fd281f3c2fae0171d2192bae8cfa4b51`, bounds
the compressed archive to 16 MiB, decompressed members to 96 MiB total, and the
staged JSON output to 256 MiB. It also caps record/text counts, rejects unsafe
ZIP paths, duplicate JSON keys and malformed source records, and sorts all
emitted rows deterministically. A surface beyond 4,096 code points or a gloss
beyond 16,384 code points fails the import rather than being silently cut off;
ordinary crossword-too-long forms within the source field bound are retained
in quarantine. Download the archive separately and run:

```sh
curl --fail --location \
  https://en-word.net/downloads/english-wordnet-2025-json.zip \
  --output /tmp/english-wordnet-2025-json.zip
shasum -a 256 /tmp/english-wordnet-2025-json.zip
uv run --no-sync python -m tools.lexicon.oewn_import \
  /tmp/english-wordnet-2025-json.zip /tmp/oewn-2025-staged.json
```

The importer preserves the source spelling and gloss, stores NFC/casefold keys,
and joins each source sense key to its OEWN synset ID and part of speech. It
keeps lexemes, inflections, senses, source references, and shape-only crossword
projections separate. Forms outside the 2–21 ASCII-letter grid shape, including
punctuation, multiword, Unicode, control/format, too-short, and too-long forms,
are retained with stable quarantine reasons. A shape candidate is not an
approved answer. Every imported sense remains semantically unreviewed; no clue
is generated and no editorial reviewer or fact verification is asserted.

The official [OEWN downloads page](https://en-word.net/downloads/) identifies
the 2025 edition date as 2025-12-31 and says OEWN is released under CC-BY-4.0.
Inspection of the exact pinned ZIP found no ZIP comment, standalone
LICENSE/NOTICE file, or metadata/manifest member; the license statement is
therefore recorded as evidence from the official download page, not as
archive-native metadata. For redistributed adapted material, the attribution
record includes the source/community, a link to CC BY 4.0, an indication that
normalization/import occurred, and no suggestion of endorsement. The actual
artifact is not checked into the repository; the URL plus pinned hash makes it
reproducible. The selected 2025 edition excludes the curated proper-noun
material that the download page describes for the separate 2025+ edition.

The output is a staging interchange file, deliberately separate from
`pack_builder.py`. It records `admissionStatus: not-admitted` and
`semanticReviewStatus: unreviewed`; importing it cannot turn its terms or
definitions into approved crossword content. A later reviewed manifest must
still pin the exact source, earn explicit licensing/admission decisions, and
provide editorial evidence before the fail-closed pack builder can emit
anything for production.

Routine importer tests create tiny hand-authored JSON ZIPs; they do not
download, embed, or import the complete OEWN corpus. The large staged export
should remain a local build artifact and must not be checked in.

## OEWN fill-only review projection

`oewn_candidates.py` accepts the pinned source archive and an actual,
separately prepared human source-terms attestation. Its executable path invokes
the importer itself, validates the imported schema, record counts, source
fingerprint, and every form/sense-to-lexeme reference, then atomically writes a
bounded review queue:

```sh
uv run --no-sync python -m tools.lexicon.oewn_candidates \
  /path/to/english-wordnet-2025-json.zip \
  /path/to/real-source-terms-attestation.json \
  /tmp/oewn-2025-fill-review.json
```

The command fails closed if the attestation is absent or malformed, the archive
is not the pinned edition, or a staged reference/count is inconsistent. It
does not create or fill in reviewer fields. The result remains
`review-required-fill-only`, `not-admitted`, and `unreviewed`; it is a review
queue, not a production lexicon or clue source. No human attestation or full
production candidate artifact has been created as part of this code change.

## Admission builder

`pack_builder.py` is a fail-closed admission tool for a separately prepared
JSON manifest. It does not read, import, or bless `source-ledger.json`, and it
does not acquire or invent a word list. In particular, the existing
`NOASSERTION` source is rejected. The manifest pins every source artifact by a
relative path and SHA-256, and records explicit SPDX, license-review,
redistribution, attribution, privacy, and admission decisions. Only allowlisted
SPDX identifiers with approved rights fields can contribute records.

The manifest includes `sources` plus `records.lexemes`, `records.senses`,
`records.facts`, and `records.clues`. Record rows carry `sourceId`,
`admissionStatus: "reviewed"`, `reviewerId`, an ISO `reviewedAt` date, and
nonempty `evidenceRefs`. A lexeme needs a reviewed surface and language. It may
also carry an explicit `personalization` object with bounded, unique
`conceptIds`, `knowledgeTaskIds`, and `associationIds`, plus an optional `pool`
of `broad` or `exploration`; these IDs are preserved in sorted order and never
inferred from prose. Invalid tags quarantine the lexeme. A sense
uses `resolutionStatus: "resolved"` with a gloss to support a clue, or
`resolutionStatus: "unresolved"` to remain fill-only. Facts must name an
admitted `lexemeId` and a reviewed statement. A clue needs its own pinned
`sourceId`, its own review metadata, exactly one `senseId` or `factId`, and a
`grammar` annotation using the repository's `clue-grammar-v1` schema. Clues
must agree with the linked lexeme's answer and pass the actual TypeScript clue
grammar validator through Node. If Node or the validator is unavailable, the
clue is quarantined while otherwise admissible fill records remain available.

Run it from the repository root:

```sh
uv run python -m tools.lexicon.pack_builder path/to/manifest.json path/to/pack.json
```

Artifact paths resolve relative to the manifest file. The builder writes a
canonical JSON pack containing pinned source and evidence provenance,
deterministically sorted records, stable quarantine reason codes, a manifest
digest, and an artifact digest. It does not establish factual truth or
production suitability: the reviewer fields and license decisions must be
earned outside this tool, and semantic/factual review remains necessary. Tests
use only explicitly synthetic, hand-authored `CC0-1.0` fixture content.
