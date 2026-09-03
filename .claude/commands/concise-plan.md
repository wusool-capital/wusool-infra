# Concise Planning

When creating an implementation plan, write it like a senior engineer handing a task to another engineer.

## Rules

- Be concise, concrete, and implementation-focused.

- Prefer short sentences and fragments.

- One numbered item = one concrete change.

- Name exact files, modules, classes, functions, or symbols whenever known.

- Explain **what changes and where**. Include **why** only when non-obvious.

- Prefer bullets over paragraphs.

- Keep each step to 1–3 sentences. Prefer 1 sentence.

- Do not narrate reasoning or describe your thought process.

- Do not restate the user's request.

- Do not explain obvious code concepts.

- Do not use filler phrases:

  - "In order to..."

  - "It is important to..."

  - "We need to make sure..."

  - "This will allow us to..."

  - "The goal of this change is..."

  - "As part of this..."

- Do not repeat the same rationale in multiple steps.

- Do not include speculative implementation details.

- If something is uncertain, state the uncertainty briefly instead of writing a long explanation.

## Structure

Use this structure:

1. **Short action title**

   - `path/to/[file.py](http://file.py)` — concrete change.

   - `path/to/[other.py](http://other.py)` — concrete change.

2. **Short action title**

   - `path/to/[file.py](http://file.py)` — concrete change.

3. **Validation**

   - Tests/checks to run.

## Example

### Good

1. **Add payment port**

   - `orders/application/ports/[payment.py](http://payment.py)` — define `PaymentPort`.

   - `orders/application/[checkout.py](http://checkout.py)` — depend on the port.

   - `orders/[bootstrap.py](http://bootstrap.py)` — adapt `BillingService` to `PaymentPort`.

2. **Update tests**

   - Add checkout tests with a fake `PaymentPort`.

   - Add the cross-module architecture rule.

3. **Validate**

   - Run `pytest orders/tests`.

   - Run architecture tests.

### Bad

1. **Introduce a payment abstraction layer**

   We need to establish a clear abstraction between the orders and billing modules. This is important because directly depending on the billing implementation would create unnecessary coupling between the two modules and make the orders use case harder to test independently. In order to address this, we should introduce a payment interface...

## Final constraint

The plan should be understandable in a 10-second scan.

If a sentence can be removed without losing an implementation decision, remove it.