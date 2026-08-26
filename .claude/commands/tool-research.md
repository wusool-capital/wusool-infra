---

name: tool-research

description: Aggressively research and recommend the single best library,

  framework, or tool to solve a specific engineering problem (e.g. "type

  safety in Python" -&gt; Pydantic, "background jobs in Python" -&gt; Celery/RQ,

  "form validation in React" -&gt; Zod/React Hook Form). Use whenever the user

  describes a problem and wants a tool/library recommendation instead of a

  from-scratch implementation, says things like "what's the best tool for X",

  "is there a library for this", "am I reinventing the wheel", "how does

  everyone else solve this", or asks to research/compare options before

  building. Also trigger proactively when you notice you're about to write

  a non-trivial amount of custom code for a problem that plausibly has a

  mature, free, open-source solution already (e.g. hand-rolled validation,

  hand-rolled retry logic, hand-rolled auth, hand-rolled caching) — surface

  this skill's findings before writing the boilerplate. Do not use this for

  vague/open-ended tech-stack decisions ("what framework should I use for my

  whole app") unless the user frames it as a scoped, specific problem.

---

# Tool Research

Find the single best tool to solve one specific, scoped problem — not a

tech-stack survey, not a listicle. The goal is a confident recommendation

the user can adopt in the next five minutes, backed by evidence, not a

vibes-based guess from training data (which may be stale on which tool

currently "won" a given space).

## Why this exists

Training data is frequently wrong about "the best tool for X" because:

- Library popularity shifts (a tool that was best-in-class two years ago

  may be unmaintained now, or superseded).

- "Which tool won" is a discoverable, verifiable fact — it does not need

  to be guessed.

- The user's actual constraints (language, framework, license, team size)

  change which answer is correct, and those constraints are usually only

  half-stated.

Always research live rather than answering from memory. Even when you're

confident you know the answer (e.g. Pydantic for Python type safety), verify

it's still current, still maintained, and still the community consensus —

"best tool" rankings can and do change.

------------------------------------------------------------------------

## Step 0: Pin down the actual problem

Before searching, restate the problem in one sentence and identify the

hidden constraints. Do not skip this even if the request seems clear — a

few seconds of scoping prevents recommending a tool that's wrong for the

user's actual stack.

Identify, from context or by asking (max one question, only if truly

blocking):

- **Language/ecosystem** (Python, TypeScript, Go, etc.) — most tools are

  ecosystem-specific, so this is almost always required.

- **The specific pain point**, not the general category. "Type safety" is

  broad — is it runtime validation of external data, static type checking,

  or schema-to-type generation? These have different best-in-class answers.

- **Hard constraints**, if stated or implied: must be free/open-source,

  must be actively maintained, must fit an existing framework (e.g. "we're

  already on FastAPI"), team size/scale.

If the user's request already contains enough of this (as in "type safety

in my Python API"), don't ask — state your interpretation in one line and

proceed. Only ask a clarifying question if the language/ecosystem is

genuinely ambiguous and guessing would waste the whole research pass.

------------------------------------------------------------------------

## Step 1: Search aggressively, from multiple angles

One search is not enough — a real research pass triangulates from several

independent signal sources so the recommendation isn't just whichever

result ranked first. Run searches covering all of the following angles,

adjusting the exact query wording to the problem:

1. **Direct "best tool for X" query** — the obvious query, useful for

   framing but not sufficient alone (SEO-gamed "best of" listicles are

   common and unreliable on their own).

2. **"X vs Y" comparisons** for any candidates that come up more than once

   — direct comparisons surface tradeoffs faster than reading each tool's

   own docs.

3. **Official docs / GitHub repo** for each serious candidate — check

   actual maintenance signal: last commit/release date, open issue

   response pattern, README claims about stability.

4. **Community sentiment** — search discussion sites (Reddit, Hacker News,

   [dev.to](http://dev.to), Stack Overflow) for the problem phrased the way a practitioner

   would phrase it, e.g. "why I switched from X to Y" or "X vs Y reddit."

   Community sentiment catches maintenance problems and rough edges that

   official docs won't admit to.

5. **Adoption/ecosystem signal** — is this tool a dependency of other

   major tools in the ecosystem, or does it show up unprompted in other

   projects' stacks? This is often a stronger signal than star count alone.

Do not stop after the first search looks conclusive. If step 1's queries

all point to the same answer, that's a good sign — confirm it holds up

under a comparison query and a maintenance check before finalizing.

------------------------------------------------------------------------

## Step 2: Evaluate every serious candidate against fixed criteria

For each candidate that survives Step 1 (usually 2-4 tools), evaluate

against these criteria. Don't skip criteria just because one tool seems

like the obvious winner — the point is to make the reasoning explicit and

falsifiable, not to confirm a first impression.

| Criterion | What to check |

|---|---|

| **Solves the exact problem** | Not a superset/subset — does it target this specific pain point, or does it require significant extra config/code to fit? |

| **Industry-standard status** | Is this what most production codebases in this ecosystem actually use? (adoption signal, not just search-result rank) |

| **Maintenance health** | Recent commits/releases, responsive issue tracker, no "looking for maintainer" notices, no long-abandoned forks being recommended over the original |

| **License &amp; cost** | Genuinely free and open-source (state the license, e.g. MIT/Apache-2.0/BSD) — flag anything with a paid tier gate on core functionality, or a license with usage restrictions (e.g. AGPL implications, "free for small teams only") |

| **Boilerplate reduction** | Does adopting it net-reduce code versus a hand-rolled solution, including the config/setup cost? A tool that trades hand-written boilerplate for equally verbose config is not a win. |

| **Integration fit** | Does it fit cleanly into the user's stated stack (framework, other libraries already in use)? |

| **Community sentiment** | Any recurring complaints (steep learning curve, breaking changes between versions, poor docs) that would change the recommendation for this user's context |

------------------------------------------------------------------------

## Step 3: Recommend one tool, not a menu

The user wants a decision, not a shopping list. Structure the answer as:

1. **The recommendation** — one tool, stated plainly, with the one-line

   reason it wins.

2. **Why it's the industry standard** (or why it isn't, if you're

   recommending a newer challenger over an incumbent — justify explicitly

   if going against the obvious/incumbent choice).

3. **License and cost** — confirm free/open-source status and license

   type.

4. **What it replaces** — the boilerplate/hand-rolled code it eliminates,

   made concrete (a short before/after sketch if it clarifies the win —

   don't write a full tutorial, just enough to show the shape of the

   savings).

5. **Quickstart** — install command and the minimal usage snippet to get

   from zero to solving the stated problem, so the recommendation is

   immediately actionable.

6. **Runner-up, briefly** — one alternative and the one-line reason it

   lost (different tradeoff, e.g. faster but less mature, more powerful

   but heavier), so the user isn't blindsided if they see it mentioned

   elsewhere. Do not give the runner-up equal weight — this is not a

   comparison table, it's a decision with a footnote.

Do not hedge with "it depends" as the final answer. If it genuinely

depends on a constraint you don't know, ask that one question in Step 0

instead of delivering a non-committal comparison at the end.

------------------------------------------------------------------------

## Example

**User**: "I need type safety in my Python API, keep having issues with bad

data coming in from clients."

**Step 0**: Ecosystem = Python. Actual pain point = runtime validation of

external/untrusted input, not static type checking (that's what the type

checker already does) — so the target category is a runtime validation

library, not a linter.

**Step 1-2** (after searching): Pydantic is the confirmed industry

standard for this in the Python ecosystem — it's the validation layer

FastAPI itself is built on, actively maintained, MIT-licensed, and the

default answer across comparison threads and GitHub adoption. Marshmallow

and attrs+cattrs come up as alternatives but consistently lose on either

FastAPI-native integration or amount of boilerplate required.

**Step 3 output**:

&gt; **Recommendation: Pydantic v2**

&gt; It's the runtime validation library FastAPI is natively built on —

&gt; zero-glue integration if you're already on FastAPI, and the de facto

&gt; standard for this exact problem in Python.

&gt; **License**: MIT, free, no paid tier gating core features.

&gt; **Replaces**: hand-written `if` chains checking types/required fields on

&gt; every incoming request body — Pydantic gives you that as a declarative

&gt; model definition instead.

&gt; **Quickstart**: `pip install pydantic` →

&gt; ```python

&gt; from pydantic import BaseModel

&gt; class UserIn(BaseModel):

&gt;     name: str

&gt;     age: int

&gt; ```

&gt; Invalid input raises a structured `ValidationError` automatically — no

&gt; manual checks needed.

&gt; **Runner-up**: `attrs` + `cattrs` — lighter-weight if you don't need

&gt; FastAPI's native integration, but requires wiring the two together

&gt; yourself where Pydantic gives you validation out of the box.

------------------------------------------------------------------------

## Guardrails

- Never recommend a tool you haven't verified is still maintained as of

  today — a tool that was standard two years ago may be deprecated now.

- Never recommend a tool solely because it appeared first in search

  results — cross-check against at least one comparison source and one

  maintenance-health check.

- If the free/open-source constraint can't be met by any strong candidate

  (rare, but happens in some domains), say so explicitly rather than

  silently recommending a paid tool.

- If the honest answer is "there are two tools that are both genuinely

  best depending on X," give the recommendation for the most likely case

  based on what's known about the user's context, and name the fork

  explicitly rather than picking one silently.