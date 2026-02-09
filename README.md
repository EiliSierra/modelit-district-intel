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
