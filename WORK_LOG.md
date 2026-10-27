# Work Log

Chronological record of merged PRs and closed issues, newest first.
Maintained by the Guide triage role; entries are append-only.

### 2026-10-27

- **PR #23**: feat: add HyperBus-class controller RTL, synthesized netlist and T1 item 1 attestation
- **Issue #13** (closed): T1 item 1 (Design sources): HyperBus controller RTL for the functional spec rows plus the synthesized netlist
- **PR #21**: feat: add behavioural HyperBus-class device model with self-test
- **PR #20**: feat: attest T1 item 10 repo hygiene via klt signoff --attest (klt 0.8.0)
- **Issue #18** (closed): T1 item 10 (Repo hygiene): attest README, LICENSE and CI with klt signoff --attest 10

### 2026-10-22

- **PR #7**: ci: add CI gate script, graded klt signoff record, README reproduce section
- **Issue #4** (closed): Repo hygiene and CI (T1 item 10): real CI checks, a graded klt signoff manifest, README spec-issue fix

### 2026-10-21

- **PR #10**: Bump Repo Skills 0.24.3 -> 0.24.7
- **Issue #11** (closed): Replace no-op package.json check/test/lint stubs that exit 0 with the real smoke gate

### 2026-10-20

- **PR #9**: test: record three-corner STA and tool versions for smoke flow
- **PR #6**: feat: add pinned RTL toolchain setup and smoke flow
- **Issue #3** (closed): Toolchain bring-up and RTL flow skeleton: pin sky130 + sky130_fd_sc_hd, lint, cocotb sim, synthesis and STA on a smoke module

### 2026-10-17

- **PR #8**: docs(spec): draft target spec, interface tables and decision records
- **PR #1**: chore(loom): Install Loom 0.19.1180
