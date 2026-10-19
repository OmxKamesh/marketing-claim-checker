# Evidence contracts

## Version 2: observation ledger (recommended for product promises)

The manifest has `version: 2`, `claims`, and `evidence` arrays. Each claim requires unique `id`, `exact_text`, `source` (path/start/end and optional sha256), `scope`, and unique `required_checks` strings. Source lines must still contain exact_text; missing or changed claim sources yield unknown.

Each observation requires unique `id`, `claim_id`, `check_id`, `scope`, `result` (`pass`, `fail`, `blocked`), `method`, `time`, `valid_until`, and `artifact` with relative path and lowercase SHA-256. Timestamps are ISO 8601 with timezone. Future observations, expiration before observation, invalid references, and duplicate observations for a claim/check are rejected. Select one current observation per required check explicitly; the tool does not silently choose among conflicting historical records.

Every required check must pass, retain an intact readable artifact, be unexpired, and match the claim scope exactly to produce `supported-in-tested-scope`. A current, applicable failure yields `contradicted`. Missing, blocked, stale or wrong-scope observations yield `unknown` absent a valid failure. Evidence retains `blocked` and `stale` statuses separately. Evidence methods and results are supplied records, not independently executed truth. The author chooses required checks and expiry; the CLI cannot establish their adequacy or honesty.

Represent a promise spanning Free and Pro with required checks for both, with the shared scope describing that overall evaluation. A Pro-only observation cannot satisfy an all-plans claim by changing its label: the agent must inspect whether the actual observation meets the declared check and scope. Structural scope equality is necessary, not semantic proof.

## Version 1: literal source assertions

A manifest has `version: 1` and `claims`, a list of objects with unique nonempty `id`, `claim`, `scope`, and optional `checks` array. Each check has `kind: "exact-lines"`, a string `expected`, and `source` containing relative `path`, one-based inclusive `start` / `end`, and optional raw-byte `sha256`.

The selected evidence root is the boundary for file reads. Absolute paths, parent traversal, and symlinks resolving outside it are rejected. Files must be UTF-8 and at most 2 MB (checked after reading; not a hostile-file resource sandbox). Line endings normalize to LF and the final file newline is ignored. Comparisons are otherwise case- and whitespace-sensitive. The optional hash checks original bytes, including line endings and BOM.

- **verified:** every supplied literal assertion matched.
- **contradicted:** at least one literal assertion differed. Other unresolved checks remain visible.
- **unknown:** no checks, unavailable files/ranges, changed pinned hashes, or unresolved checks without a contradiction.
- Invalid schema or paths abort without a partial ledger (exit 2). A ledger containing contradictions or unknowns exits 1; all verified exits 0. Empty claim arrays are invalid (exit 2) in both versions.

These statuses apply to explicitly scoped assertions. Exact text does not validate truth, causality, security, legal compliance or actual product behavior. Claims that require those observations must remain unknown in the human assessment. A test log may be stale or fabricated; record provenance and do not grant it authority automatically.

Reports omit source content by default. `--include-excerpts` adds expected and actual text to JSON, not Markdown. Claim/scope text and file paths are still included. Hashes identify evidence, not trusted provenance. Never publish real customer data, credentials, or private source without authority.
