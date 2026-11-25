# AI Interactions Log

> **Stretch features only.** These sections cover the optional challenges I attempted: Challenge 1 (advanced song features), Challenge 2 (multiple scoring modes), Challenge 3 (diversity penalty), and Challenge 4 (visual summary table). The AI assistant was Claude Code, working in my project folder.

---

## Agentic Workflow (SF8): Challenge 1, Advanced Song Features

**What task did you give the agent?**

Add five or more new song attributes to `data/songs.csv`, then update the loader and scoring so the recommender uses them. I also asked it to do all four optional challenges in one pass, then explain what it did and how it works.

**Prompts used:**

These are summaries of my instructions, not word-for-word copies:

- "Once you've made the necessary changes and commits, push everything, then go straight ahead and do all the optional challenges and let me know what you did and how it works."
- Earlier in the project I set the working style: the AI proposes edits, and I approve or revise them. For the challenges I told it to go ahead without asking first.

**What did the agent generate or change?**

- `data/songs.csv`: five new columns on all 18 songs: `popularity` (0-100), `release_decade`, `detailed_mood` (nostalgic, aggressive, euphoric, dreamy, and others), `instrumentalness` (0-1), and `language`.
- `src/recommender.py`:
  - `load_songs` converts the new numeric fields and tolerates files that don't have them.
  - `Song` and `UserProfile` gained optional fields (default `None`), so the original tests still work.
  - A new helper scores the new attributes: decade match (half points one decade away), detailed mood match, popularity closeness, instrumental fit, and language match. A feature only counts if the user profile asks for it.
- `src/main.py`: two extra profiles ("Dreamy Instrumental Study" and "Nostalgic Throwback") that use the new attributes, run with `--advanced`.
- `tests/test_recommender.py`: new tests for type conversion and for the advanced scoring.
- `README.md`: an "Optional Extensions" section with real output.

**What did you verify or fix manually?**

- **Nothing broke:** I saved the output of the seven original profiles before changing the code, then compared it after. The two outputs were identical (using the plain list format, now `--list`), so the extra features don't change old results. Where a preference is missing, the new code adds zero.
- **Math check:** the advanced test adds up the expected bonus by hand (0.5 + 0.75 + 0.5 + 0.25 + 0.25 = 2.25) and checks the program's total matches.
- **Reading the output:** the "Dreamy Instrumental Study" profile put *Library Rain* first, with decade, detailed mood, and instrumental bonuses showing in its reasons, which matched what I expected.
- **A test of mine failed** (see Challenge 3 below), and the cause was the test data, not the code.

---

## Design Pattern (SF10): Challenge 2, Multiple Scoring Modes

**Which design pattern did you use?**

A simple **Strategy pattern**. Each ranking strategy ("balanced," "genre_first," "mood_first," "energy_focused") is a small `ScoringMode` object that holds four weights. The scoring code doesn't know which strategy it is using; it just reads the weights it is given.

**How did AI help you brainstorm or implement it?**

I asked for a design that keeps the code modular. The AI suggested treating a mode as data (a frozen dataclass of weights) instead of writing a separate scoring function for each mode, because only the weights differ. That avoids copy-pasted scoring code and means a new mode is a single line. It also suggested keeping the original weight constants as the "balanced" mode, so default behavior and every earlier result stay the same.

**How does the pattern appear in your final code?**

- `ScoringMode` and the `MODES` dictionary at the top of `src/recommender.py`.
- `score_song(user_prefs, song, mode)` and `recommend_songs(..., mode=...)` both take the mode (a name or a `ScoringMode`). An unknown name raises a `KeyError`, and a test checks that.
- `--mode` in `src/main.py` lets the user switch modes from the command line.

**Verification notes:** I ran all four modes on several profiles. The #1 song rarely changes; the modes mostly reorder the middle of the list. For example, `mood_first` puts *Rooftop Lights* above *Gym Hero* for High-Energy Pop, and `energy_focused` puts *Storm Runner* above *Rooftop Lights*. A test uses two hand-made songs to check that `genre_first` and `energy_focused` choose different winners.

---

## Challenge 3: Diversity Penalty

**Prompt (summary):** penalize a song's score if its artist is already in the top recommendations, so the results don't repeat one artist or genre.

**What the AI generated:** `_rerank_with_diversity` in `src/recommender.py`. It picks songs one at a time. Before each pick, a candidate loses 1.0 point if its artist was already picked and 0.5 points if its genre was already picked. The penalty is added to the song's list of reasons so the user can see why it moved. It is off by default (`diversity=False`) and turned on with `--diverse`.

**What I verified or fixed:**

- With the flag off, the output is exactly the same as before.
- With it on, Genre Not in Catalog swaps *Gym Hero* for *Storm Runner* and *Night Drive Loop* (same artist as *Sunrise City*) for *Neon Overdrive*. For Chill Lofi, the second LoRoom song drops one place.
- **A failing test:** my first diversity test expected a same-genre, same-mood repeat to lose to a rock song. It didn't, because even after losing the full 1.5 points it still scored 2.94 against 2.40. That showed the penalties are mild compared to a genre match (2.0), which is by design, so I rewrote the test to compare against a different artist in the same genre.
- The editor flagged that the best candidate could be `None`; it can't happen inside the loop, so I added an `assert` that says so.

---

## Challenge 4: Visual Summary Table

**Prompt (summary):** show results as a formatted table, and make sure each row includes the reasons for its score.

**What the AI generated:** `format_table` in `src/main.py`. I chose plain ASCII formatting instead of the `tabulate` library, so there is nothing extra to install. Each row shows rank, title, artist, score, and one line per reason, with long reasons wrapped. It is the default output; `--list` switches back to the plain list format.

**What I verified:** a test checks that the table contains the title, score, and every reason. I also ran it by itself and together with `--diverse` and checked that the penalty lines wrap cleanly.

---

# Final Project: Agentic Workflow Enhancement

**Task given to the assistant (Claude Code).** Extend the Module 3 recommender into an applied AI system: an agent that takes a plain-English request, retrieves glossary documents, plans a taste profile, runs the existing recommender, critiques its own answer and revises it, with guardrails, logging and an evaluation harness.

**Working style.** Plan first, then implement: I asked for a plan, approved or redirected it (offline planner instead of an LLM; skip the optional specialization stretch), and then had Claude build it. Prompts, summarized:

- "Check whether Phase 0 (repo copy and folders) was completed correctly and take Phase 1 into account."
- "Draft the Phase 1 plan."

**What the agent does at each step.** Every request produces a trace of the steps below. The complete set of traces for all 20 evaluation requests is committed at [assets/agent_traces.md](assets/agent_traces.md) (regenerate with `python -m evaluation.run_eval --traces assets/agent_traces.md`); two are embedded here.

1. `guardrail`: validate the request
2. `retrieve`: find matching glossary and catalog documents
3. `plan`: build the taste profile from them
4. `recommend`: run the original scorer
5. `critique`: confidence and issues
6. `revise`: fix issues (max 2) and go back to step 4
7. `decide`: status `ok` / `needs_review` / `no_match` / `rejected`

### Trace: a request that needs a revision to remove repetition

**coding-negated-loud**

Request: `late-night coding, nothing too loud, a bit dreamy`

```text
1. guardrail: request accepted (49 chars)
2. retrieve: 3 usable chunk(s): Coding [activities.md] via 'coding', catalog detailed_mood: dreamy [catalog] via 'dreamy', Louder [modifiers.md] via 'loud' (negated, so its effect is flipped)
3. plan: genre=lofi, mood=focused, energy=0.25, acoustic=True, mode=balanced, diversity=False
4. recommend: mode=balanced, top=Focus Flow
5. critique: confidence 0.89 (high) [fit 0.81, evidence 1.00, separation 1.00]; issues: repetitive
6. revise #1: top results repeat an artist or genre; turned the diversity penalty on
7. recommend: mode=balanced, top=Focus Flow
8. critique: confidence 0.89 (high) [fit 0.81, evidence 1.00, separation 1.00]
9. decide: status=ok, confidence=0.89, revisions=1

Top 3: Focus Flow (4.24); Library Rain (3.58); Midnight Coding (2.44)
```

### Trace: a request the catalog cannot satisfy (revision, then human-review flag)

**guard-genre-missing-kpop**

Request: `k-pop hits`

```text
1. guardrail: request accepted (10 chars)
2. retrieve: 1 usable chunk(s): K-pop [genres.md] via 'k-pop'
3. plan: genre=k-pop, mood=None, energy=0.5, acoustic=False, mode=balanced, diversity=False
4. recommend: mode=balanced, top=Velvet Hours
5. critique: confidence 0.12 (low) [fit 0.37, evidence 0.33, separation 0.18]; issues: genre_not_in_catalog, low_fit, repetitive
6. revise #1: genre 'k-pop' is not in the catalog; dropped it and rely on mood and energy instead
7. revise #1: top results repeat an artist or genre; turned the diversity penalty on
8. recommend: mode=balanced, top=Velvet Hours
9. critique: confidence 0.45 (low) [fit 0.85, evidence 0.00, separation 0.47]
10. decide: status=needs_review, confidence=0.45, revisions=1

Top 3: Velvet Hours (1.28); Block Party Anthem (1.16); Night Drive Loop (1.14)
```

**Verification.** The agent was checked by running it, not by reading it: a smoke test of 15 realistic requests exposed four real defects (negation broken by the stemmer, a too-generic trigger word, a critic that rewarded dropping the user's genre, and a repetition check that fired on requested genres). Each was fixed and given a regression test; details are in `model_card.md`, Sections 13 and 15.

