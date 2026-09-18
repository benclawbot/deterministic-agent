# Example LAWS.md for the grounded-citations skill

Every claim in a research summary must trace back to a URL. No orphan
assertions, no "common knowledge" claims without a source.

## LAW: every_claim_has_url
- require: claims len>= 1
- require: claims.0.url has "://"
- message: every claim must have a URL; bare assertions are not allowed

## LAW: urls_are_unique
- require: urls len>= 1
- message: research summary must cite at least one URL

## LAW: no_duplicate_urls
- require: urls len== 1
- message: URL list must be deduplicated (enforced upstream)
