# V2 Golden Fixture Quality Review

| fixture | score | score sanity | blockers/red-flags | rec alignment | likely FP/FN note |
|---|---:|---|---|---|---|
| career_gap | 68.28 | pass | pass (employment_gap, generic_language) | pass |  |
| job_hopping | 45.29 | pass | pass (generic_language, job_hopping) | pass |  |
| junior | 56.05 | pass | pass (none) | pass |  |
| manager | 77.03 | pass | pass (none) | pass |  |
| mid_level | 78.57 | pass | pass (none) | pass |  |
| overlapping_roles | 68.30 | pass | fail (employment_gap, job_hopping) | pass | Likely FP: overlap profile flagged as gap |
| senior | 81.74 | pass | pass (none) | pass |  |
| weak_formatting | 38.50 | pass | fail (none) | pass | Likely FN: no red flags on clearly weak resume |
