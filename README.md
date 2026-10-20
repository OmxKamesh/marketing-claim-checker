# Promise Check

**Your launch copy makes promises. Which ones have evidence?**

Promise Check turns local documentation claims into an inspectable evidence ledger. It distinguishes a matching source assertion, a contradiction, and an unknown instead of treating absent evidence as proof. The portable CLI has no dependencies, network access or project-code execution.

## Try it in 30 seconds

Requires Python 3.10 or newer. From this repository:

```sh
python scripts/promise_check.py examples/claims.json --root examples
python scripts/promise_check.py examples/claims.json --root examples --format json
python -m unittest discover -s tests -v
```

The demo intentionally returns exit **1**, with **1 verified, 1 contradicted, 1 unknown**:

| Claim | Evidence | Result |
| --- | --- | --- |
| Inventory lists CSV and JSON | product.txt:1 matches | verified |
| Inventory says team size 50 | product.txt:3 says 20 | contradicted |
| Product has 99.99% uptime | No measurement supplied | unknown |

Before: three confident statements. After: one precise source assertion, one wording correction to review, and one measurement request. No invented customer or browser observations.

## Install as a Claude Code skill

Copy this repository's contents into `~/.claude/skills/promise-check/` for personal use, or `.claude/skills/promise-check/` in a chosen project. Keep `SKILL.md`, `scripts/`, and `references/` together. Then explicitly invoke:

```text
/promise-check docs/product-overview.md
```

Automatic model invocation is disabled. The skill guides the agent in scoping claims and authoring a manifest; the Python helper deterministically verifies literal assertions. Other agents can run the CLI without implying native skill compatibility.

## Write a ledger

For recorded product tests use the **version 2 observation ledger**. Each original claim retains its source lines, scope and required checks. Each observation records pass/fail/blocked, method, timestamp, expiry and artifact hash. Only complete current evidence with matching scope yields `supported-in-tested-scope`; it does not mean independently verified product truth. Stale and blocked evidence remain explicit. A Free-plan failure cannot be hidden behind a Pro-plan pass.

```sh
python scripts/promise_check.py examples/observations.json --root examples --format json
```

This synthetic observation demo returns a contradiction while its records are current (through 2027-10-01); after expiry it correctly becomes unknown with stale evidence. No real product was tested by the fixture.

Start from `examples/claims.json`. Choose an evidence root and relative paths. Include source line ranges and a narrow scope for each claim. Optionally pin each source's SHA-256 to detect changed evidence. Full schema and status semantics: [contract](references/contract.md).

Use `--output new-report.json --format json` to save a report; existing files are never overwritten. JSON includes source paths, line ranges, hashes, statuses and reasons; Markdown provides a readable review. Exit codes: 0 all supplied assertions verified/supported, 1 unknown or contradicted assertions, 2 invalid input. Empty claim arrays are rejected as invalid input (exit 2). Markdown reports escape supplied text; JSON retains original data.

## What this does not prove

Literal checks prove what local text says, not whether a product actually delivers it. A matching test log is not an independently rerun test. This tool deliberately avoids browser automation, semantic truth scoring, runtime execution and external account access. The agent must not mark a broad promise verified merely because a weaker local assertion matches. Missing evidence stays unknown.

This complements documentation linters and onboarding auditors: its focus is an explicit, reproducible assertion ledger with evidence fingerprints, rather than prose quality or quickstart execution. It does not claim to be the first claim-audit tool.

Outputs may include sensitive claim text or paths even when excerpts are off. Review before sharing. All bundled examples are synthetic. License: MIT, see [LICENSE](LICENSE).

Claude skill references: [official skills documentation](https://code.claude.com/docs/en/skills), [Agent Skills engineering overview](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).

---

Built by Kamesh Jindal at [OMX Digital](https://omxdigital.ai). Part of the [OMX Claude Skills toolkit](https://github.com/OmxKamesh/claude-code-skills). Need this set up for your business? [kamesh@omxdigital.ai](mailto:kamesh@omxdigital.ai)
