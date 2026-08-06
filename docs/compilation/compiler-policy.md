# Compiler Policy 1.0.0

The Stage 06 compiler policy is a closed execution contract. Unknown fields,
missing fields, and any value that differs from the implemented behavior are
rejected before SHACL, OWL reasoning, or artifact construction begins.

The compiler accepts `xsd:date` only as `YYYY-MM-DD` and verifies that the
calendar date exists. It accepts `xsd:dateTime` only as
`YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DDTHH:MM:SS.fractionZ`, with a real calendar
date, a valid 24-hour time, seconds, and the literal `Z` UTC designator. Timezone
offsets, local times, date-only dateTimes, dateTime values used as dates, and
cross-datatype coercion are forbidden. RDFLib parsing is not a lexical
validation authority.

The policy freezes canonical N-Triples and N-Quads as authoritative, fixed
Turtle and TriG as human-readable views, UTF-8 encoding, and LF endings. It also
freezes the `foundation-instance` SHACL profile, RDFS inference, recording of
warnings and infos, blocking of violations, and prohibition of automatic
repair. OWL consistency is required; UNKNOWN and NOT_RUN fail. Business ABox,
modeling provenance, and review audit graphs remain separate.
