# Work Log

Chronological record of merged PRs and closed issues, newest first.
Maintained by the Guide triage role; entries are append-only.

### 2026-11-23

- **Issue #114** (closed): Remove toolchain smoke flow: make smoke duplicates what the controller flow now exercises
- **PR #216**: chore: remove the smoke flow the controller flow now covers
- **Issue #103** (closed): Stop restating six toolchain pins in docs/environment.md: a hand-maintained copy nothing checks
- **Issue #160** (closed): Replace check_pdk_root.py (329-line shell parser) with a 4-line runtime assertion
- **Issue #170** (closed): Bump the klayout-tools pin 0.8.0 -> 0.9.2 and regenerate the records and signoff render under it
- **Issue #171** (closed): T1 item 7 (Post-layout verification): SDF-annotated run of the controller benches on the post-route netlist
- **Issue #172** (closed): Post-route multi-corner STA record with the RWDS strobe clock (hb_rwds_i) declared (the timing half of T1 item 5)
- **Issue #181** (closed): Remove the duplicate netlist freshness run from fleet layout regeneration
- **Issue #187** (closed): Locate the first command/address mismatch on the 50 MHz SDF-annotated post-route CK path
- **Issue #189** (closed): Item-7 SDF freshness gate does not bind the SDF to the DEF it was produced from
- **Issue #190** (closed): ROADMAP item-7 completion criterion does not name the partial SDF annotation (504 TIMINGCHECK entries dropped)
- **Issue #192** (closed): STA.md no longer reproduces from sta_note(): pre-layout note generator widened without re-minting the record
- **Issue #199** (closed): Bench pad-sample position (+5 ns after each CK edge) double-counts the real CK delay under SDF annotation
- **Issue #200** (closed): cfg_read's fixed 1 ns settle races the annotated cfg_rdata mux (no_calibration false failure)
- **Issue #204** (closed): ROADMAP still says the annotated run fails 43/43 after the cfg_read settle fix
- **Issue #205** (closed): Pin-edge bench sampling (HRBENCH_SAMPLE_NS=0) reads DQ/RWDS in the CK edge's own timestep with no settling sync
- **Issue #208** (closed): No freshness gate binds sim/hyperram/records/STA.md to sta_note(): the pre-layout record can silently drift again
- **Issue #212** (closed): scripts/check_ci.sh step 7 passes when klt signoff downgrades a met T1 item to stale_evidence
- **Issue #70** (closed): Remove drifted layout/toolchain.json inventory and stale bring-up stubs
- **Issue #84** (closed): Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy
- **PR #175**: data: regenerate the layout-chain records and GL report at klt 0.9.2
- **PR #183**: docs: point environment.md pins at their defining scripts
- **PR #186**: flow: post-route multi-corner STA record with the RWDS strobe clock declared (issue #172)
- **PR #188**: verify: SDF-annotated post-route bench run (T1 item 7 probe) — CK-path finding, design iteration filed
- **PR #191**: fix: reject repo-local PDK roots before fleet regeneration
- **PR #194**: docs: name the partial SDF annotation beside ROADMAP item 7's done-criterion
- **PR #195**: fix: bind the SDF gate to the DEF it was produced from
- **PR #196**: chore: drop the drifted layout/toolchain.json inventory and stale #3 comments
- **PR #197**: fix: drop the standalone netlist freshness run from fleet regeneration
- **PR #198**: chore: drop the vendored tier doc; the pinned klt selects the checklist
- **PR #201**: Post-route CK/CA pin trace: refuted ICG/tap-chain cause; divergence located at bench sample position
- **PR #202**: fix: sample on the annotated CK pin edge in the ctrl bench
- **PR #203**: fix: settle cfg_read 2 ns for the annotated cfg_rdata mux
- **PR #207**: docs: re-mint pre-layout STA.md corner tables from the widened sta_note renderer
- **PR #209**: feat: bind pre-layout STA.md to its record with sta-note/sta-check CI gate
- **PR #210**: docs: mark the #200 cfg-read settle fixed in ROADMAP item 7 residuals
- **PR #211**: fix: settle the offset-0 pad sample in the CK edge timestep
- **PR #213**: ci: reject signoff records with stale_evidence downgrades in step 7

### 2026-11-22

- **Issue #178** (closed): Use a temporary venv for the pinned-Yosys test fixture
- **PR #180**: check: build the yosys-gate fixture's python3 as a real venv

### 2026-11-18

- **PR #168**: docs: remove un-closed Issue #101 entry from WORK_LOG
- **Issue #167** (closed): WORK_LOG.md: the pre-#166 Issue #101 entry lacks (closed) and truncates the title, leaving #101 logged twice
- **Issue #101** (closed): Share the tap delay line: hr_dq_out and hr_rd_capture build the same 16-cell chain twice
- **PR #164**: fix: match backslash-escaped heredoc delimiters in check_pdk_root
- **Issue #162** (closed): check_pdk_root.py: a backslash-escaped heredoc delimiter (cat << EOF) still truncates the ensure_pdk body
- **PR #159**: fix: make check_pdk_root body extraction heredoc-aware
- **Issue #158** (closed): check_pdk_root.py: a bare } inside a heredoc truncates the ensure_pdk body and hides a repo-rooted PDK_ROOT
- **PR #156**: guard: assert ensure_pdk never exports a repo-rooted PDK_ROOT
- **Issue #155** (closed): check_ci.sh: no guard that fleet-regen-layout.sh provisions the PDK outside the repo root
- **PR #154**: fix: provision the fetched fleet PDK outside the repo root so evidence decks record scope external
- **Issue #142** (closed): fleet-regen-layout.sh: provision the PDK outside the repo root so deck.path in committed evidence is resolvable
- **PR #152**: docs: re-point g_rwds_dly/g_ck_dly citations at hr_tap_delay's g_dly chain
- **Issue #150** (closed): Stale g_rwds_dly / g_ck_dly generate-label citations after the hr_tap_delay refactor
- **PR #149**: docs: replace false stale-layout status paragraph in README
- **Issue #147** (closed): README status paragraph: 'Layout-dependent items are stale' is false since #140, and quotes a netlist hash #101's regen replaces
- **PR #148**: refactor: share the 16-cell tap delay line in one hr_tap_delay module
- **PR #145**: docs: remove misplaced 2026-11-18 WORK_LOG section holding un-closed Issue #52 entry
- **Issue #144** (closed): WORK_LOG.md: misplaced 2026-11-18 section records Issue #52 as opened, out of chronological order
- **PR #140**: data: regenerate routed layout and layout-dependent evidence from the post-#51 netlist
- **Issue #52** (closed): Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48)

### 2026-11-15

- **PR #136**: ci: replace check_help_text.py with an inline shell assertion in check_ci.sh
- **Issue #133** (closed): Remove check_help_text.py: a 200-line checker guarding a two-line sed already fixed structurally
- **PR #131**: fix: restore committed delay-chain records after derive_cmd refusal cases
- **Issue #128** (closed): check_delay_chain_derive.py's derive_cmd cases write the committed records into the running checkout when a guard regresses
- **PR #132**: fix: delete an unused DRIVER_SCRIPTS constant from the --help checker (module since removed by #133)
- **Issue #130** (closed): the --help checker defined an unused DRIVER_SCRIPTS constant; the real driver list lives in check_ci.sh
- **PR #129**: fix: pattern-anchor the shell drivers' --help sed bound, gate it in CI
- **Issue #124** (closed): run-opensta.sh --help range is a hardcoded line number that must be hand-bumped on every arg-loop edit
- **PR #126**: docs: correct stale proof-status lines in target-spec and README
- **Issue #100** (closed): Correct three status lines the tree has outrun (spec/README decision list, target-spec proof note, README ladder)
- **PR #125**: fix: refuse partial reports in delay_chain derive, keep its provenance; name ngspice version in setup-env
- **Issue #113** (closed): setup-env reports ngspice as a masked value; delay_chain.py derive lacks the sim path's partial-collection and provenance guards
- **PR #123**: pad-sta: make --pdk-root DIR work, harden pdk_ok, align RECORD.md with committed artifacts
- **Issue #116** (closed): sim/pad-sta: four record/driver polish items found reviewing PR #108
- **PR #121**: ci: run the delay-chain derivation unit check in check_ci.sh
- **Issue #117** (closed): Wire scripts/check_delay_chain_derive.py into check_ci.sh: a passing unit check nothing runs
- **PR #120**: docs: take Now/Next workflow state out of ROADMAP prose
- **Issue #111** (closed): docs/ROADMAP.md: date the Now list to the header sha so merge-queue drift stops blocking review
- **PR #119**: check: assert bench declarations for every verification/ subdirectory
- **Issue #106** (closed): Bench-coverage assertion stops at verification/ctrl/: smoke and hyperram_model can still ship an undeclared bench
- **PR #118**: docs: reword stale TBD(src) citations in the verification tree and regrade T1 item 9
- **Issue #110** (closed): Stale TBD(src) citations in the verification tree after PR #94 filled every device-param row
- **PR #108**: evidence: pad-liberty STA record - OpenSTA sees through the pads, no in-window fast corner
- **Issue #98** (closed): Answer spec open question (a): do the pinned PDK's sky130_fd_io liberty views give OpenSTA arcs through the pad cells?
- **PR #109**: feat: ngspice 45-corner RWDS delay-chain campaign; spec question (b) answered at the schematic level
- **Issue #99** (closed): Answer spec open question (b): ngspice per-tap delay of the RWDS delay chain across the decision-0004 corners

### 2026-11-14

- **PR #104**: chore: ignore the GL=1 cocotb build directory, not just sim_build/
- **Issue #91** (closed): GL bench run leaves an untracked sim_build_gl/ directory (.gitignore covers sim_build/ only)
- **PR #96**: docs: roadmap as of 2026-11-13
- **PR #107**: feat: add a hyperram-sta verb recording STA at all 16 shipped liberty corners
- **Issue #97** (closed): Record pre-layout STA of the current controller netlist at every shipped sky130_fd_sc_hd corner
- **PR #105**: refactor(verification): glob the controller bench list and assert the item-9 inventory covers it
- **Issue #93** (closed): Derive the controller bench list from disk: three hand-maintained copies, none checked
- **PR #95**: fix: gate synthesis on the pinned yosys.wasm hash, not just its version
- **Issue #89** (closed): flow/hyperram.py yosys gate checks the engine version string, not the pinned wasm build
- **PR #94**: docs(spec): transcribe the device timing table and refresh both sibling comparisons
- **PR #90**: test: flag a CK-phase error in the device model instead of ignoring the level
- **Issue #86** (closed): Device model ignores the CK level it is passed: check edge polarity or drop the parameter

### 2026-11-13

- **PR #87**: fix: reject an off-pin yosys in flow/hyperram.py and re-mint the netlist under the pin
- **Issue #81** (closed): Committed gate-level netlist does not reproduce under the pinned yosys, but item 1 records the freshness check as passed
- **PR #82**: test: randomize RWDS extra latency on random-traffic reads, drop can't-fail checks
- **PR #83**: refactor: run flow/ synthesis and place-and-route through scripts/klt.sh
- **Issue #77** (closed): Remove stale extra-latency workaround, can't-fail assertions and dead helpers from the controller benches
- **Issue #80** (closed): Route flow/ runners through scripts/klt.sh: synthesis and place-and-route still use unpinned klt
- **PR #79**: refactor: derive device-model placeholder values from one shared constant
- **PR #76**: refactor: resolve klt through one pinned wrapper script
- **Issue #73** (closed): Consolidate the six klt version pins and three klt resolvers into one
- **Issue #72** (closed): Consolidate the two divergent PLACEHOLDER device-model parameter sets into one
- **PR #74**: docs: point layout README's STALE note at the current 2am#7142 hold
- **Issue #71** (closed): layout/README.md still says #52 is held on 2AMLogic/2am#6416 (closed)

### 2026-11-12

- **PR #66**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-07

- **PR #62**: Bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #60**: test: run controller benches on the committed gate-level netlist
- **Issue #59** (closed): Run the controller benches on the committed gate-level netlist (zero delay, PDK cell models)

### 2026-11-05

- **PR #57**: docs: correct README status to 7 of 11 and flag stale layout records
- **Issue #56** (closed): README status is stale: item 9 is met and layout evidence predates the #48 RTL fix

### 2026-11-03

- **PR #54**: docs: document register space as even-words-only (decision 0007)
- **Issue #49** (closed): Odd device register words (ID1/CR1) unreachable from host: document or add addressing

### 2026-11-02

- **PR #51**: fix: flush read capture ring through ST_LAT for extra-latency reads
- **PR #50**: test: add controller benches per CT row and T1 item-9 attestation
- **Issue #48** (closed): RTL: extra-latency reads capture a spurious word (RWDS falls after CA)
- **Issue #14** (closed): T1 item 9 (Testbenches shipped): behavioural device model and one cocotb test per CT spec row

### 2026-11-01

- **PR #46**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-29

- **PR #43**: docs: escape pipes in clock-phase table header cell
- **Issue #42** (closed): spec: escape pipes in |e_nom| table header in clock-phase-requirement.md
- **PR #41**: docs: add write-path CLK90 phase and jitter requirement
- **Issue #39** (closed): Record the CLK/CLK90 timing requirement for the sky130-pll quadrature-output decision (sky130-pll#332, DR-010)

### 2026-10-28

- **PR #37**: docs: update README status and reproduce steps to match graded evidence
- **Issue #36** (closed): T1 item 10 (repo hygiene): README says 'nothing is designed yet' and reproduces none of the graded results — update status and reproduce steps, re-attest

### 2026-10-27

- **PR #34**: build: pin klayout-tools to PyPI 0.8.0 in setup-env
- **Issue #32** (closed): Bump klayout-tools pin b61f753d0369 → 0.8.0
- **PR #29**: feat: add klt erc supply report and cite it as T1 item 11
- **Issue #19** (closed): T1 item 11 (Power delivery): klt erc supply spec, PDN response and LVS power match for the controller
- **PR #28**: feat: add clean klt drc report for routed GDS as T1 item 3
- **Issue #16** (closed): T1 item 3 (DRC clean): klt drc on the routed controller GDS
- **PR #27**: feat: add gate-level LVS of the routed controller as T1 item 4 evidence
- **Issue #17** (closed): T1 item 4 (LVS clean): klt lvs against the gate-level netlist with power_connectivity
- **PR #25**: feat: add routed controller layout and T1 item 2 envelope via klt place-and-route
- **Issue #15** (closed): T1 item 2 (Layout): klt place-and-route of the controller core with a PDN, committed routed GDS
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
