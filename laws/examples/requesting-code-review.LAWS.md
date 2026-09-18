# LAWS.md for the requesting-code-review skill

Every finding MUST cite a file:line. This is non-negotiable — findings without
locators cannot be reproduced, retried, or verified.

## LAW: every_finding_cites_location
- require: findings len>= 1
- require: findings.0.file has ":"
- message: at least one finding required, and first finding must include "file:line"

## LAW: severity_is_canonical
- require: findings.0.severity in {critical,high,medium,low,nit}
- message: severity must be one of {critical, high, medium, low, nit}

## LAW: no_finding_without_repro
- require: findings.0.reproducer len>= 10
- message: every finding must include a reproducer (commands, inputs, or steps) of at least 10 chars

## LAW: findings_sorted_by_severity
- require: findings.0.severity in {critical,high}
- message: highest-severity findings must appear first; this skill sorts output by severity desc
