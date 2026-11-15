# Partners components

`routes/partners.tsx` lists partners (PRD PA1 to PA3) at `/partners?category=...&partner=<id>&panel=edit|lead`.

| File | Notes |
| --- | --- |
| `partner-drawer.tsx` | Record drawer: website profile, internal terms behind Show terms, leads referred; Edit and publish with a website preview; New referred lead |

Public fields mirror the website's Sanity `partner` documents; terms live in the Engine database only. Demo data lives in `demo/partners-data.ts`.
