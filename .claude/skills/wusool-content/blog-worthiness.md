# Blog-worthiness check

Decides whether a piece is worth publishing as an Insights article, before any Sanity
work. Insights only: reports are gated lead magnets and skip this check.

It reads only, never writes to Sanity or Webflow. The verdict is advice: the person can
override it, and you note the override in `checks.md`.

Work on `source.md` in the code tool. For HTML input, strip the tags first:
`sed 's/<[^>]*>//g' source.html > source.md`.

## 1. Readability (measured, not guessed)

Same limits as the Wusool docs style: headings ≤ 12 words, paragraphs ≤ 100,
sentences ≤ 25. Run in the code tool; each prints only the offenders.

```bash
# Headings over 12 words
grep -E '^#{1,6} ' source.md | awk '{ if (NF - 1 > 12) print NF - 1 ": " $0 }'
# Paragraphs over 100 words (headings, list items and table rows excluded)
grep -vE '^(#|[-*] |[0-9]+\. |\|)' source.md | awk -v RS= '{ if (NF > 100) print NF ": " substr($0, 1, 60) }'
# Sentences over 25 words
grep -vE '^(#|[-*] |[0-9]+\. |\|)' source.md | tr '\n' ' ' | sed 's/[.!?] /&\n/g' | awk '{ if (NF > 25) print NF ": " substr($0, 1, 60) }'
# Length: under 400 words is thin for a search-led article
wc -w < source.md
```

If `vale` is on PATH, you may also run it, but these four checks are the requirement.
List each hit in `checks.md`; they're fixes to suggest, not a reason to reject.

## 2. Duplicate topic

Pick the article's main topic keyword (two or three words). Then check both places:

1. Sanity:

   ```groq
   *[_type == "insights" && title match $kw]{title, "slug": slug.current}
   ```

2. Webflow: the Webflow connector's CMS **list collection items** action on collection
   `69aaa645fa60624091050e8e`, filtering `name` by `contains` the keyword, with `limit: 5`.
   Read only each item's name and slug: the items carry full article bodies.

A close match isn't a rejection: say which article it overlaps and how this one differs,
or suggest updating the existing one. Without the Webflow connector, write
"Webflow duplicate check **not run**" in `checks.md`, and tell the person in one line.

## 3. Rubric

Score each from 0 to 2, with one line of reasons quoting the text where possible.

| # | Criterion | 2 | 1 | 0 |
|---|---|---|---|---|
| 1 | **Audience and silo** | Clearly for GCC business owners, buyers or investors; fits one `silo` | Fits loosely | Off-topic for Wusool |
| 2 | **Search intent** | Answers one question people search; title and h2s follow it | Topic clear, intent vague | No identifiable query |
| 3 | **Substance** | GCC-specific facts, numbers, examples or first-hand deal experience | Some specifics, mostly general | Generic advice found anywhere |
| 4 | **Actionable** | The reader knows what to do next | Partly | Opinion or news only |
| 5 | **Credibility** | Fits one of the listed authors; claims are sourced or first-hand | Some unsourced claims | Unverifiable numbers or claims |
| 6 | **Path to a CTA** | Leads naturally to `/sell`, `/valuation-tool` or a report | A CTA would feel bolted on | No sensible CTA |

## 4. Verdict

- **Publish:** 10–12, and no 0.
- **Revise:** 7–9, or a 0 on criteria 2, 4, 5 or 6. List the smallest fixes that would
  raise the score.
- **Don't publish:** 6 or less, or a 0 on criterion 1 or 3.

Write the scores, verdict, readability hits and duplicate findings to the top of
`checks.md` under `## Blog-worthiness`.

Show the person only this, in plain words (no rubric table, no criterion numbers):

- The verdict and score, in one line ("Publish: 11/12.").
- Each criterion that lost points, one line each, saying why.
- A close duplicate, if found, in one line.
- On **Revise**, the fixes that would change the verdict, most important first.
  Readability hits stay in `checks.md` unless they're a main problem.

- **Publish:** carry on with `insights.md`.
- **Revise or Don't publish:** ask whether to stop, revise first, or go ahead anyway.
  Going ahead is their call; record it as an override.
