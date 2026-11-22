---
name: lit
description: Use when searching, adding, citing or organizing literature, or editing the .bib, in a research-kit project.
---

# Literature

**No citation from memory (hard rule).** Every reference is verified against a retrieved source (the publisher's page, `https://doi.org/<doi>`, or the PDF) before it enters the `.bib`, `notes/lit/map.md`, the notes, the paper or the slides. Authors, year, title, venue and DOI come from that source, never from memory. If no source can be retrieved, stop and report.

## The `.bib`

The `.bib` that the manuscript's main file names (with `\bibliography` or `\addbibresource`; the main file may be in a subfolder such as `paper/draft/`) is the only reference store.

1. Each new entry is built from its retrieved source and carries a `doi` or `url` field from that source.
2. After any `.bib` edit or new `\cite`, run:
   ```
   "${CLAUDE_PLUGIN_ROOT}/bin/kit" check_bib.py --project "${CLAUDE_PROJECT_DIR}"
   ```
   - `missing from .bib: <key>` (exit 1): add the verified entry, or fix the `\cite`.
   - `no DOI or URL: <key>`: add the field from the retrieved source.
   - Exit 2: stop and ask.
3. The `.bib` is in the paper repo. Commit it there, and push to Overleaf with approval.

## The literature map: `notes/lit/map.md`

Entries are grouped by strand (`##` headings). One line per reference:

```markdown
- `key` — one-line claim — threads: RQ1, RQ3 — unread | skimmed | read
```

Every key in the map is in the `.bib`. A new strand is added with approval.

## Searches: `notes/lit/searches/YYYY-MM-DD-topic.md`

Save each deep-research run (the `deep-research` skill, or a search done here) with the question, the date and every source with its URL. Search files are records and are never rewritten. A reference moves from a search file into `map.md` and the `.bib` only after the user has reviewed it, and only after it is verified as above.

## PDFs

Save PDFs to `notes/lit/pdfs/<key>.pdf`. Git ignores that folder.

## Done when
- [ ] Every new reference was verified against a retrieved source, whose URL or DOI is in its `.bib` entry.
- [ ] `check_bib.py` exits 0 and lists no new entry without a DOI or URL.
- [ ] New map entries and strands were approved, and their keys are in the `.bib`.
- [ ] Search results reached `map.md` only after the user's review.
- [ ] `.bib` changes were committed, and pushed unless the user declined.

## Stop and ask
- No source can be retrieved for a reference.
- The retrieved source disagrees with an existing `.bib` entry.
- `check_bib.py` exits 2.
