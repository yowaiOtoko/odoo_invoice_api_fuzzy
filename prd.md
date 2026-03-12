# Product Requirements Document: Odoo Addon — Quotations and Invoices with Product Names or IDs

## Introduction/Overview

External systems that create quotations or customer invoices in Odoo often send a list of products. When products are identified by name, the caller usually has to resolve each name to a product id (and UoM) via multiple RPC calls, then call the standard creation API. That logic is duplicated outside Odoo and causes many round-trips.

**Goal**: Provide an Odoo addon that accepts a single request to create either a **quotation** (sale.order) or a **customer invoice** (account.move) with a list of line items where each product can be specified by **name** or by **id**. The addon resolves or creates all products on the backend, then creates the document using standard Odoo code with the resolved ids. The entire flow is server-side in one request.

## Goals

1. **Primary**: Expose APIs that create a quotation or an invoice from a payload containing a list of products identified by name or id; all product resolution and creation happens backend-side for both document types.
2. **Secondary**: For items given by name: search for an existing product by name, or create one with sensible defaults (default UoM rule); for items given by id: validate and use the product. No product resolution logic required on the caller side.
3. **Tertiary**: Reuse standard Odoo document creation (sale.order for quotations, account.move for invoices) so business rules, validations, and workflows remain unchanged.

## User Stories

1. **As an API consumer**, I want to send one request to create a quotation with a list of product names or ids so that I get a created quotation without resolving products or calling multiple APIs myself.

2. **As an API consumer**, I want to send one request to create a customer invoice with a list of product names or ids so that I get a created invoice without resolving products or calling multiple APIs myself.

3. **As an Odoo administrator**, I want new products created from names to use a defined default UoM (e.g. from an existing service or any product) so that the catalog stays consistent.

4. **As an integrator**, I want to mix names and ids in the same request (e.g. two lines by name, one by id) and have the backend resolve everything before creating the quotation or invoice.

## Functional Requirements

### Document types and entry points

1. **Two document types**: The addon must support creating:
   - **Quotations**: sale.order (draft quotation) with sale.order.line.
   - **Customer invoices**: account.move with move_type `out_invoice` (or equivalent) with invoice lines (account.move.line linked to the move).

2. **Entry points**: The addon must expose at least two callables, invokable via XML-RPC/JSON-RPC:
   - One that creates a **quotation** (e.g. `create_quotation` or `create_quote` on sale.order or a dedicated model).
   - One that creates a **customer invoice** (e.g. `create_invoice` on account.move or a dedicated model).
   Alternatively, a single method that accepts a document type parameter (e.g. `document_type`: `'quotation'` | `'invoice'`) is acceptable if it keeps the contract clear.

### Payload and resolution (common to both)

3. **Payload — line items**: Each method must accept a list of line items. Each line item must allow the product to be specified in either of two ways:
   - **By name** (string): backend will search for a product by name (e.g. `ilike`); if not found, create it using the default UoM rule, then use the resulting product id and uom_id for the line.
   - **By id** (integer): backend will validate that the product exists and is usable, then use it for the line.

   Line items may include additional fields as needed (e.g. quantity, unit price, discount), consistent with standard sale order lines or invoice lines.

4. **Payload — document header**: Each method may accept header data appropriate to the document type:
   - **Quotation**: e.g. partner_id, company_id, validity date.
   - **Invoice**: e.g. partner_id, company_id, journal_id, invoice_date, payment_reference.
   Required vs optional and defaults follow standard Odoo behavior for the document type.

5. **Backend resolution**: For each line item (same logic for quotation and invoice):
   - If product is given by **id**: ensure the product exists and the user can use it; fetch uom_id from the product. If invalid or missing, raise a clear error.
   - If product is given by **name**: call internal “search or create” logic: search `product.product` by name (ilike, limit 1); if found, use that product’s id and uom_id; if not found, create a new product (template + variant) with the default UoM rule and use the new variant’s id and uom_id.

6. **Default UoM rule (when creating from name)**: When creating a new product from a name, resolve default UoM in this order:
   - UoM of an existing product with `type == 'service'` (one such product); if none,
   - UoM of any existing product (one product, any type); if none,
   - First UoM from `uom.uom` (e.g. search with empty domain, limit 1).
   If no UoM can be resolved, raise a clear error for that line.

7. **Create document**: After resolving all line items to product ids and uom_ids:
   - **Quotation**: Create using standard Odoo logic (create `sale.order`, then create `sale.order.line` with resolved product_id, uom_id, and any other provided line fields).
   - **Invoice**: Create using standard Odoo logic (create `account.move` with move_type out_invoice, then create `account.move.line` invoice lines with resolved product_id, uom_id, and any other provided line fields). Do not bypass standard validations, onchanges, or posting workflows.

8. **Response**: Each method must return enough for the caller to identify the created document (e.g. id and/or name/reference). Optionally return created line ids or a minimal representation of the document.

9. **Errors**: Clear errors when:
   - A product id is invalid or not found.
   - A product name is empty or not provided where name is used.
   - Default UoM cannot be resolved when a product must be created from a name.
   - Document creation fails (permissions, validations, ORM errors).

10. **Permissions**: The methods must respect Odoo access rights (e.g. read/create products, read UoM, create sale orders and lines for quotation; create account.move and lines for invoice). Unauthorized use must fail with standard Odoo-style errors.

11. **Idempotency (product by name)**: Multiple lines with the same product name in one request must resolve to the same product (one search-or-create per distinct name); calling the API again with the same names must reuse existing products, not create duplicates.

### Internal: search or create (product by name)

12. **Search**: Match by name using a case-insensitive substring match (e.g. domain `[['name', 'ilike', name]]` on `product.product`, limit 1). Return that variant’s id and uom_id if found.

13. **Create**: If not found, create one product (template + variant) with the given name, type (e.g. default `'service'`), list_price 0 or configurable default, and UoM from the default UoM rule. Return the new variant’s id and uom_id. This logic is shared internally by both quotation and invoice creation; it does not need to be a separate public RPC unless desired for reuse.

## Non-Goals (Out of Scope)

1. **UI**: No new UI (views, menus, wizards) required; API-only.
2. **Standalone “search or create” RPC**: The main contract is “create quotation or invoice with list of names/ids.” A separate public RPC that only returns product_id/uom_id for a name is optional.
3. **Bulk product resolution only**: No API that only resolves a list of names to ids without creating a document in v1.
4. **Fuzzy matching**: Matching by name is ilike only; no synonyms or fuzzy matching.
5. **Pricing**: No pricelist or automatic pricing in the addon beyond passing through quantity/price if provided; list_price for new products can be 0 or a simple default.
6. **Multi-variant products**: Create path is one variant per template; no attribute-based variants.
7. **Other document types**: Credit notes, refunds, or purchase orders are out of scope for v1 unless explicitly added later.

## Technical Considerations

1. **Models**: Quotation method on or alongside `sale.order`; invoice method on or alongside `account.move`. Shared resolution and search_or_create logic in a common helper (e.g. on product.product or a small utility model).
2. **Resolution loop**: Same for both: for each line, if product is id → validate and read uom_id; if product is name → call internal search_or_create, get product_id and uom_id. Build line vals for the relevant model (sale.order.line or account.move.line).
3. **Standard creation**: Use standard `sale.order` / `sale.order.line` for quotations and standard `account.move` / `account.move.line` for invoices; do not bypass validations or required onchanges.
4. **Invoice specifics**: Ensure journal, company, and partner are set as required by Odoo; invoice lines may need account and other fields populated per standard (e.g. via onchange or default computation).
5. **Version**: Target the Odoo version(s) in use; account for differences in sale.order, account.move, and product API across versions.
6. **Logging**: Log when products are created from names and when quotations or invoices are created for auditing.

## Success Metrics

1. **Single request**: Caller can create a quotation or an invoice with a list of product names and/or ids in one request; all resolution and document creation happens server-side.
2. **No client-side resolution**: Callers do not need to perform product search, UoM resolution, or product create RPCs before calling these APIs.
3. **Consistency**: New products created from names use the defined default UoM rule; standard Odoo logic is used for both quotation and invoice creation.
4. **Stability**: No duplicate products for the same name; clear errors for invalid ids, empty names, or unresolved default UoM; both document types behave predictably.

## Open Questions

1. Exact method names and models: e.g. `sale.order.create_quotation()` and `account.move.create_invoice()` vs a dedicated wrapper model with both methods.
2. Line item payload shape: how to distinguish name vs id (e.g. `product_name` vs `product_id`); same shape for quotation and invoice lines where possible.
3. Optional line fields: quantity (default 1?), unit price, discount, description; and whether new products created from name support a type (service/consu) per line.
4. Header fields: required vs optional for quotation (e.g. partner_id) and invoice (e.g. partner_id, journal_id, invoice_date).
5. Return format: e.g. `{'id': int, 'name': str}` or minimal record; same style for both document types.
6. Odoo version(s) to support and tests for sale.order, account.move, and product APIs.
