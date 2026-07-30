# TM Forum field review

**Sources (Apache-2.0 GitHub mirrors):**
- https://github.com/tmforum-apis/TMF629_CustomerManagement (Customer Management v5.0.1 OAS reviewed via public README/schema paths)
- https://github.com/tmforum-apis/TMF637_ProductInventory
- https://github.com/tmforum-apis/TMF620_ProductCatalog

TM Forum assets are **OpenAPI/JSON schemas**, not OWL ontologies. Mapping is exclusively via `mappings/tmf_to_mnp.yaml`.

## Adopted (MVP)

| Source | Field / object | MNP target | Notes |
|--------|----------------|------------|-------|
| TMF629 | Customer | mnp:Subscriber | related |
| TMF629 | Customer.account / relatedParty | mnp:TelecomAccount / relatedAccount | broader/related |
| TMF637 | Product | mnp:ServiceSubscription | related |
| TMF637 | Product.productOffering | mnp:TelecomService | related |
| TMF637 | Product.status | mnp:subscriptionStatusCode | narrower; eligibility still uses NUMBER_STATUS evidence |
| TMF620 | ProductOffering | mnp:TelecomService | related |

## Simplified

- ProductSpecification vs ProductOffering collapsed into one `TelecomService` class for MVP (`in_mvp: false` for specification mapping).
- Polymorphic `relatedParty` reduced to account linkage.

## Not used for eligibility

- Customer contact medium, payment method catalogs, geographic site, full product characteristic arrays, notification endpoints.
- These are useful CRM/inventory fields but not required for the five MNP eligibility rules in this demo.

## Explicit non-claims

- No `owl:equivalentClass` between TMF JSON schema objects and MNP classes.
- No vendored OpenAPI files in this MVP (mapping documented; `local_path: null`). If downloaded later, retain LICENSE + URL + version + commit.
