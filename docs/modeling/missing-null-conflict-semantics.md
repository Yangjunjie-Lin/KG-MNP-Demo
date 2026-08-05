# Missing, Null, and Conflict Semantics

The Stage 04 invariant is absence is not negation.

| State | Representation | Generator behavior |
|---|---|---|
| Absent optional field | no member | no issue |
| Absent expected field | declaration or rule | warning `MISSING_INFORMATION` |
| Absent required-for-proposal field | declaration or rule | blocking `MISSING_INFORMATION`; incomplete Proposal may still be returned |
| Explicit null | JSON member with `null` and `presence: NULL` | preserve null state; never coerce |
| Unknown | `presence: UNKNOWN` | review issue; not null |
| Redacted | `presence: REDACTED` | review issue; not absence |
| Conflict | all declared alternatives | blocking `CONFLICT`; no winner |

No missing field produces a negative fact. No conflict is resolved by source
order or confidence. Unmapped fields remain review items and never mint a new
class or property.

