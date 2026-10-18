# 5-minute demo / viva script

**Goal:** show the full chain denial → policy → evidence → cited appeal → tracked outcome, then the engineering behind it.

## 0:00 Problem (30 s)
"Insurers deny many claims; most are never appealed because writing the appeal is slow. Pramaan AI automates the research and drafting, and a human approves."

## 0:30 Public site (30 s)
- Home page: point at the **live counters** (codes in dataset, policies indexed, appeals generated). "These come from the database through `/api/public/stats`, not hard-coded."
- Open **Resources → Denial code guide**, search `authorization`. "That is the official CARC/RARC/EOB dataset."

## 1:00 Billing Portal (90 s)
1. *Log in → Billing Portal → Create account.* Mention httpOnly cookies, CSRF, 2FA option.
2. Dashboard is empty → **Load sample data** (fictional). Charts and deadline badges appear.
3. **Denials**: sort by amount, filter by payer, select two rows → **Run analysis** (bulk). Show win estimates and the "policy none found" badge for the second sample file.
4. Open the MRI claim → *Analysis and appeal*: **criteria met / partial / missing**, "To strengthen this appeal".

## 2:30 The appeal (60 s)
- **Generate appeal** (under 1 s). Show the three columns: letter | policy clauses | chart evidence.
- **Click `[P1]`**: the source clause highlights. "Every sentence is traceable."
- Edit the letter (autosave "Saved"), then **PDF packet**: show the **PRAMAAN AI watermark**, packet ID and appendices.

## 3:30 Closing the loop (45 s)
- Set status **Won**, enter recovered amount → dashboard **Recovered** updates; **Timeline** shows every step; bell shows the status change.
- Say: "The win percentage is labelled *synthetic* until 50 real outcomes exist; `scripts/train_predictor.py` then retrains it."

## 4:15 Patient Portal + safety (30 s)
- Patient signup → 5-step wizard with autocomplete → letter in first person.
- Try opening `#/b` as a patient: redirected. Mention per-organisation policy libraries and admin-only console.

## 4:45 Engineering talking points (15 s)
De-identification before the LLM, citation guard, refresh-token replay detection, 53 tests with all external services mocked, Docker + PostgreSQL + Alembic, CI.

## Likely questions
- *Why not just use ChatGPT?* Grounding: it can only cite retrieved policy text and chart sentences; unsupported citations are rejected.
- *Is the win rate real?* No. It is explicitly an estimate on synthetic data until retrained on real outcomes.
- *HIPAA?* Prototype only. See the README warning.
- *What if no policy exists?* The letter states that honestly and relies on chart evidence.
