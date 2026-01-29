# Nettest Phase 4: TUI & Documentation Updates

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update TUI with new features (VoIP, bufferbloat, ISP evidence, CSV export) and update all documentation.

**Architecture:** Enhance interactive.py menu, add VoIP/health display to monitor.py, update wizard.py, and update scripts.md + troubleshooting.md.

**Tech Stack:** Python 3.8+, Rich library.

---

## Task 1: Update Interactive Menu with New Options

**File:** `scripts/nettest/tui/interactive.py`

Add new menu options and settings:

1. Update menu to include new options:
```
  [cyan]6[/cyan]  VoIP quality test  [dim]- Test call quality (MOS score)[/dim]
  [cyan]7[/cyan]  ISP evidence       [dim]- Generate ISP complaint report[/dim]
```

2. Add `bufferbloat` and `export_csv` to settings dict

3. Handle choices 6 and 7:
   - Choice 6: Run ping + calculate MOS, show VoIP suitability
   - Choice 7: Full test + generate evidence report

4. In custom test, add questions for:
   - "Run bufferbloat test?"
   - "Export CSV files?"

**Commit:** `feat(tui): add VoIP and ISP evidence options to interactive menu`

---

## Task 2: Enhance Monitor Mode with Health Score

**File:** `scripts/nettest/tui/monitor.py`

1. Import `calculate_mos_score` and `calculate_connection_score`

2. Add health score calculation after ping results

3. Update dashboard to show:
   - Overall health score (0-100) with grade
   - VoIP MOS score
   - Color-coded status based on thresholds

4. Add new columns or summary row for:
   - Connection Health: [score]/100 [grade]
   - VoIP Quality: [MOS] ([quality])

**Commit:** `feat(tui): add health score and VoIP quality to monitor dashboard`

---

## Task 3: Update Wizard with New Settings

**File:** `scripts/nettest/tui/wizard.py`

1. Add new step after logging for "Quality Tests":
   - Enable bufferbloat detection?
   - Enable VoIP quality calculation?

2. Add step for "Export Options":
   - Default export format (HTML only, HTML + CSV, all)
   - Export directory

3. Update summary to show new settings

**Commit:** `feat(tui): add quality tests and export options to wizard`

---

## Task 4: Update scripts.md Documentation

**File:** `docs/scripts.md`

Add sections for:

1. **Features list** - Add:
   - Connection Health Scoring
   - VoIP Quality Assessment (MOS)
   - ISP Complaint Evidence
   - Bufferbloat Detection
   - CSV Export

2. **Command-Line Arguments** - Add:
   - `--bufferbloat` - Run bufferbloat detection test
   - `--export-csv` - Export results to CSV files

3. **New section: Connection Health Scoring**
   - Explain the 0-100 score
   - Grade breakdown (A+ to F)
   - Component scores (speed, latency, stability)

4. **New section: VoIP Quality Assessment**
   - MOS score explanation (1.0-5.0)
   - Quality ratings
   - Suitability for HD Voice, Video, etc.

5. **New section: ISP Complaint Evidence**
   - What it generates
   - How to use for ISP complaints
   - Copy button in HTML

6. **New section: CSV Export**
   - Files created
   - Format description

7. **Interactive Mode** - Update options list with new choices

8. **HTML Report** - Update to mention:
   - Health gauge
   - VoIP quality section
   - ISP evidence section
   - Route heatmap

**Commit:** `docs: update scripts.md with new nettest features`

---

## Task 5: Update troubleshooting.md

**File:** `docs/troubleshooting.md`

1. **Network Diagnostics** - Update command examples to show new flags

2. **New section: Contacting Your ISP**
   - How to use ISP evidence report
   - What to say to technical vs non-technical support
   - Key metrics to mention

3. **New section: VoIP/Video Call Issues**
   - Use MOS score to diagnose
   - Thresholds for different call types
   - Recommendations based on quality

**Commit:** `docs: add ISP complaint and VoIP troubleshooting guides`

---

## Task 6: Test and Push

Run tests:
- `python3 -m nettest --interactive` - verify new menu options
- `python3 -m nettest --monitor --interval 10` - verify health display
- `python3 -m nettest --wizard` - verify new wizard steps

Push all changes.
