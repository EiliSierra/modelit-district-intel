# ModelIt District Intelligence System

Sales intelligence system for ModelIt K12 targeting California school districts through LCAP analysis, board meeting scrapes, contact mapping, and entry strategy development.

## Methodology

1. **LCAP Extraction** - Parse Local Control Accountability Plans for STEM/science spending, funding sources, and strategic priorities
2. **Board Meeting Scrape** - Extract approved spending, vendor contracts, curriculum adoptions, and partnership agreements from public board meeting agendas/minutes
3. **Contact Mapping** - Identify decision-makers (superintendents, STEM coordinators, board members) with verified emails
4. **Vendor/Partner Analysis** - Map current curriculum publishers, EdTech platforms, PD providers, and industry partners
5. **Science Curriculum Audit** - Document adopted programs by grade band, adoption year, and next adoption cycle
6. **Entry Strategy** - Develop tailored outreach approach referencing specific LCAP goals and budget pathways

## Directory Structure

```
_templates/           # Reusable templates for new districts
_reference/           # CA education system reference docs
districts/            # One folder per district
  rialto-usd/        # Pilot district
    profile.md        # Full intelligence profile
    lcap-extract.md   # LCAP budget extraction
    board-meetings.md # Board meeting scrape
    contacts.md       # Decision makers
    science-curriculum.md
    vendors-partners.md
    entry-strategy.md
    pitch-notes.md
    docs/             # Downloaded PDFs
comparison.xlsx       # Cross-district tracking
pipeline.md           # Sales pipeline
```

## Key Data Sources

| Source | URL | Data |
|--------|-----|------|
| District LCAP | District website | Budget, priorities, actions |
| Board Agendas/Minutes | District website | Approved spending, contracts |
| Ed-Data.org | ed-data.org | Financials, demographics |
| CDE DataQuest | dq.cde.ca.gov | Test scores, enrollment |
| CAASPP (EdSource) | caaspp.edsource.org | Proficiency rates by subgroup |
| CDE School Dashboard | caschooldashboard.org | Performance indicators |

## Districts

| District | Status | Entry Contact | Next Step |
|----------|--------|---------------|-----------|
| Rialto USD | Research Complete | Juanita Chan-Roden | Schedule intro call |

## ModelIt Value Proposition

ModelIt K12 is an NSF SBIR-funded computational modeling platform that enables students to build, simulate, and analyze systems models. It aligns with:
- **NGSS**: Science & Engineering Practices (developing/using models, computational thinking)
- **CA Math Framework**: Mathematical modeling, data analysis
- **LCAP Goals**: Math proficiency improvement, STEM equity, college/career readiness
- **CTE Pathways**: Biotech, engineering, health science modeling applications

## Collaborators

| Name | GitHub | Role |
|------|--------|------|
| Dr. Charles Martin | charlesmartinedd | Lead |
| Dr. Marie Martin | ginjack2002 | Co-Lead |
| Eili Sierra | EiliSierra | Project Coordinator |

---

## How to Add a New District

### Quick Start

1. Open Claude Code in this repo folder
2. Copy the prompt from [`DISTRICT-INTEL-PROMPT.md`](DISTRICT-INTEL-PROMPT.md)
3. Replace `[DISTRICT NAME]` with the district (e.g., "Fontana Unified School District")
4. Replace `[STATE]` with the state (e.g., "California")
5. Paste into Claude Code and press Enter
6. Claude will research, create all files, update the spreadsheet, commit, and push

### What Gets Created

For each district, Claude generates **9 files** in `districts/[district-slug]/`:

| File | Purpose |
|------|---------|
| `README.md` | Quick reference card with key metrics and "Why This District" |
| `profile.md` | Full intelligence profile (demographics, test scores, STEM programs, budget) |
| `contacts.md` | Decision makers organized by tier with verified emails |
| `board-meetings.md` | Board meeting index with links and extraction templates |
| `lcap-extract.md` | LCAP/budget extraction with funding sources and entry points |
| `science-curriculum.md` | Current science curriculum by grade band with competitive analysis |
| `vendors-partners.md` | Vendor/partner map with warm intro paths |
| `entry-strategy.md` | Tailored 5-phase sales approach with timeline |
| `pitch-notes.md` | Email templates, talking points, objection handling |

Plus updates to `comparison.xlsx` (8 sheets) and `pipeline.md`.

### Example

To add Fontana USD:

```
I need you to build a complete district intelligence profile for
**Fontana Unified School District** in **California** for the
ModelIt K12 district sales system.

[rest of prompt from DISTRICT-INTEL-PROMPT.md]
```

### Priority Districts

| District | County | Why | Priority |
|----------|--------|-----|----------|
| San Bernardino City USD | San Bernardino | Nearby, large (~48K), similar demographics | High |
| Fontana USD | San Bernardino | Dr. Alvarez's previous district | High |
| Sweetwater UHSD | San Diego | Large (~39K), high Hispanic, South Bay | High |
| Vista USD | San Diego | Local, high Hispanic enrollment | Medium |
| Oceanside USD | San Diego | Local, Camp Pendleton connection | Medium |
| Compton USD | Los Angeles | Dr. Alvarez worked here previously | Medium |
| Escondido Union HSD | San Diego | Local to Carlsbad | Medium |
| National School District | San Diego | 90%+ Hispanic, National City | Medium |
