# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**VibeMatch 1.0**

---

## 2. Intended Use  

**Goal.** VibeMatch suggests the 5 songs from a small catalog that best fit one person's taste. It does not predict what a real listener will play next. It scores each song against what the user says they like: favorite genre, favorite mood, target energy, and whether they like acoustic music.

**Intended use.**

- Classroom exploration of how a recommender turns data into a ranked list.
- Learning how scoring rules, weights, and ranking work together.
- It assumes the user can describe their taste in one genre, one mood, and one energy level.

**Not intended for.**

- Real listeners or a real music app. The catalog has only 18 songs.
- Judging songs, artists, or genres. A low score means "does not match this profile," not "bad music."
- Any setting where fairness matters. It cannot learn from behavior, and it treats every pair of genres as equally different.

---

## 3. How the Model Works  

Every song gets points for how well it fits the user. Then the songs are sorted, and the top 5 are shown.

- **Genre match:** +2.0 points if the song's genre is the user's favorite.
- **Mood match:** +1.0 point if the song's mood is the user's favorite.
- **Energy closeness:** up to +1.0 point. The closer the song's energy is to what the user wants, the more points. A song that is too loud and a song that is too quiet are both penalized.
- **Acoustic fit:** up to +0.5 points. If the user likes acoustic music, acoustic songs get more. If not, non-acoustic songs get more.

The highest possible score is 4.5. Each point is recorded with a short reason, so every recommendation can explain itself.

Changes from the starter: I added the acoustic score, made genre and mood matching ignore capital letters, and kept all the weights in one place so they are easy to change for experiments.

**Optional extras.** These are all off by default, so the results above do not change unless one is switched on.

- **Scoring modes:** "genre first," "mood first," and "energy focused" change the weights.
- **Diversity penalty:** a song loses points if its artist (1.0) or genre (0.5) is already in the list.
- **Advanced preferences:** a user can also ask for a decade, a detailed mood, a popularity level, instrumental or vocal, and a language.
- **Table view:** results can be printed as a table that includes the reasons.

---

## 4. Data  

- **Size:** 18 songs. The starter had 10, and I added 8.
- **Variety:** 15 genres and 14 moods. Examples are pop, lofi, rock, jazz, hip hop, classical, EDM, metal, reggae, and folk.
- **What each song has:** genre, mood, energy, tempo, valence, danceability, and acousticness. I later added five more: popularity, release decade, a detailed mood tag (like "nostalgic"), instrumentalness, and language. The core scoring uses genre, mood, energy, and acousticness. The new attributes only count when a user asks for them.
- **Limits:** 13 of the 15 genres have only one song. Only 3 songs have middle energy (between 0.43 and 0.74). There is no "sad" mood. There are no lyrics. The numbers, including popularity and decade, are made up for the simulation and were not measured from real audio or real listening.

---

## 5. Strengths  

- Quiet and loud tastes get completely different lists. Chill Lofi and Deep Intense Rock share no songs at all.
- Chill Lofi works very well. All of its top three songs are lofi.
- For Deep Intense Rock, the #1 pick (*Storm Runner*) matched my own intuition.
- Every result comes with plain reasons, such as "genre match (+2.00)," so it is easy to see why a song ranked where it did.

---

## 6. Limitations and Bias 

The system keeps recommending *Gym Hero* to almost everyone who wants high energy. It showed up in the top 5 for 5 of my 7 test profiles, even for a user who asked for "happy pop." Gym Hero is very energetic and not acoustic, so it earns near-full points for energy and for the "not acoustic" bonus, no matter what else the user wants. Genre is worth twice as much as the best energy score, but there is only one rock song and two pop songs, so once the genre match runs out, energy alone fills the list. This creates a small filter bubble: loud, high-energy songs crowd out everything else for anyone who likes energetic music.

Another gap: the catalog has no "sad" mood at all. A user who wants sad songs gets matched on energy only, so the mood they asked for is ignored.

---

## 7. Evaluation  

**Profiles tested.** I tested seven profiles and looked at the top 5 songs for each. The full output is in the README.

- Standard: High-Energy Pop, Chill Lofi, Deep Intense Rock
- Adversarial: Sad but Energetic, Genre Not in Catalog, Acoustic EDM, Dead-Center Energy

I also ran one experiment: I turned the mood weight to 0 and ran all seven profiles again (details in the README). Removing mood made High-Energy Pop put *Gym Hero* ahead of *Sunrise City*, which is worse for someone who asked for "happy." So mood matters, and the original weights were better.

**What surprised me.**

- *Iron Throne* (metal) ranks below EDM and pop for a rock fan. The genre rule only checks for an exact match, so it cannot see that metal is close to rock.
- "Sad but Energetic" gets the same five songs as "Deep Intense Rock," just in a slightly different order. With no genre or mood match, the system just picks the loudest songs.
- The Acoustic EDM user says they like acoustic music, but still gets a song with almost no acoustic sound at #1. The acoustic bonus is too small to matter much.

**Comparing every pair of profiles.** "Shared" is how many of the 5 songs appear in both lists.

| Pair | Shared | What changed, and why it makes sense |
|--------------------------------|---|-----------------|
| High-Energy Pop vs. Chill Lofi | 0 | Loud pop turns into quiet lofi. The energy targets are 0.5 apart and the genre is different. |
| High-Energy Pop vs. Deep Intense Rock | 4 | Both want loud songs. Only the #1 changes (Sunrise City vs. Storm Runner). Gym Hero is #2 for both: for pop it matches the genre, for rock it matches "intense." |
| High-Energy Pop vs. Sad but Energetic | 4 | The sad profile has no genre or mood match, so loudness picks the songs. Pop gets Rooftop Lights (a "happy" match); the sad profile gets Iron Throne (louder). |
| High-Energy Pop vs. Genre Not in Catalog | 3 | With no pop to match, scores drop from about 4.3 to 2.4. But "happy" and energy 0.8 still bring up Sunrise City and Rooftop Lights, which is a sensible fallback. |
| High-Energy Pop vs. Acoustic EDM | 4 | Both want very loud songs, so the lists are alike. The EDM profile just puts Neon Overdrive first because of its genre match. |
| High-Energy Pop vs. Dead-Center Energy | 0 | Energy 0.9 vs. 0.5, and pop vs. jazz. Nothing overlaps, which is correct. |
| Chill Lofi vs. Deep Intense Rock | 0 | Opposites: quiet acoustic songs vs. loud intense ones. This is the clearest proof that the scoring separates "chill" from "intense." |
| Chill Lofi vs. Sad but Energetic | 0 | Quiet songs vs. the loudest songs in the catalog. Energy is the main reason. |
| Chill Lofi vs. Genre Not in Catalog | 0 | Energy 0.4 vs. 0.8 and "chill" vs. "happy," so the lists do not meet. |
| Chill Lofi vs. Acoustic EDM | 0 | Both say they like acoustic music, yet the lists share nothing. Energy outweighs the acoustic preference, which shows how small that bonus is. |
| Chill Lofi vs. Dead-Center Energy | 1 | Both want lower energy and share Coffee Shop Stories. Lofi has three matching songs, so its top 3 are all lofi. Jazz has only one, so its list drops off after #1. |
| Deep Intense Rock vs. Sad but Energetic | 5 | Same five songs. "Rock/intense" gets Storm Runner first because it matches genre and mood. "Blues/sad" matches nothing, so Gym Hero (loudest) goes first. |
| Deep Intense Rock vs. Genre Not in Catalog | 2 | Both like high energy, but the k-pop profile wants 0.8 and "happy," so it shifts toward Sunrise City and Rooftop Lights. They share only Gym Hero and Sunrise City. |
| Deep Intense Rock vs. Acoustic EDM | 4 | Very similar energy targets (0.92 and 0.95). The only real difference is which genre match comes first: Storm Runner or Neon Overdrive. |
| Deep Intense Rock vs. Dead-Center Energy | 0 | Energy 0.92 vs. 0.5, and rock vs. jazz. They want different music. |
| Sad but Energetic vs. Genre Not in Catalog | 2 | Neither matches a genre. The sad profile ranks by energy 0.9, the k-pop profile also uses "happy," so only Gym Hero and Sunrise City overlap. |
| Sad but Energetic vs. Acoustic EDM | 4 | Both want very loud songs. The EDM profile has one genre and mood match (Neon Overdrive) and the rest of the list looks the same. |
| Sad but Energetic vs. Dead-Center Energy | 0 | Energy 0.9 vs. 0.5. Nothing is shared, which is expected. |
| Genre Not in Catalog vs. Acoustic EDM | 2 | Energy 0.8 vs. 0.95 and "happy" vs. "euphoric." They share only Rooftop Lights and Gym Hero. |
| Genre Not in Catalog vs. Dead-Center Energy | 2 | They share Block Party Anthem and Night Drive Loop. With no genre match, or only one, both lists fill up with songs near the energy target. |
| Acoustic EDM vs. Dead-Center Energy | 0 | Energy 0.95 vs. 0.5, EDM vs. jazz. Opposite tastes. |

---

## 8. Future Work  

1. **Smarter genre matching.** Treat close genres as partly matching, so metal counts as near rock instead of being treated like any other genre.
2. **Learn from behavior.** Use skips, replays, and playlists instead of only what the user says they like, so the weights can be tuned from real feedback.
3. **A bigger, more balanced catalog.** Add many more songs, more middle-energy songs, and missing moods such as "sad."

(I already added a diversity penalty as an optional extra. It helps, but it only swaps songs in the top 5. It cannot fix a catalog that is too small.)

---

## 9. Personal Reflection  

**Biggest learning moment.** I learned how a system can turn preferences into recommendations. My version only uses what the user *says* they like. Real apps also watch what people actually do, such as skips, replays, and playlists, and learn from that. That gap between stated taste and observed behavior was the biggest thing I took away.

**How AI helped, and when I double-checked it.** AI helped me plan the scoring rules, write the code, and find weak spots. But I did not trust the numbers on their own. I recalculated scores by hand and compared them to the program's output. I also caught problems that the AI had not predicted. For example, running `main.py` directly from my editor gave a `FileNotFoundError`, because the data path depended on where I ran it from. Some editor warnings were also out of date, so I checked by actually running the code and the tests.

**What surprised me.** A handful of simple rules produced lists that felt like real recommendations. Chill Lofi looked just right. But the same simple rules also made *Gym Hero* show up for almost every high-energy user. It looks like taste, but it is just arithmetic. That is how a small bias can look like a personal recommendation.

**What I would try next.** I went on to try all four optional challenges: more song features, different scoring modes, a diversity rule, and a clearer results table. They helped, but they did not fix the deeper limits: the catalog is tiny, and genre is matched exactly. Next I would try smarter genre matching, a much bigger catalog, and a version that learns from what a user actually plays or skips.


---
---

# Part 2: Applied AI System Extension (Final Project)

Sections 1-9 above describe the original VibeMatch 1.0 recommender. The sections below cover what was added for the final project: a plain-English **agent** that retrieves glossary documents, plans a profile, recommends, critiques its own result and revises. Setup, architecture and run evidence are in [README.md](README.md).

## 10. What Changed

| Added | What it does |
|---|---|
| Retriever (RAG) | Looks up glossary documents ([data/knowledge/](data/knowledge/)) and the catalog's vocabulary to translate the user's words into a taste profile |
| Planner | Builds the profile from what was retrieved, and records every assumption |
| Critic | Scores confidence (fit, evidence, separation) and detects problems such as a requested genre that is not in the catalog |
| Revise loop | Up to 2 fixes: drop an unmatched genre/mood, switch scoring mode, turn on the diversity penalty |
| Guardrails + logging | Refuse unsafe or malformed input safely; log each step to `logs/agent.log` |
| Evaluation harness | 20 predefined requests with pass/fail, confidence, retrieval on/off comparison, repeatability |

The scoring engine from Sections 1-9 is unchanged. The AI feature changes how a request is *understood and checked*, not how songs are scored.

## 11. Limitations and Biases (Agent)

- **The glossary is my opinion.** "Studying" maps to lofi, "workout" maps to pop, "date night" maps to R&B, "beach" maps to reggae. These are stereotypes. A person who studies to metal, or works out to country, is told what they "should" want. Each activity maps to exactly one genre, so the system cannot represent that taste varies.
- **Keyword matching is brittle.** It understands only words I wrote down. "Something for when I miss summer" is not understood. Ambiguous words can mislead: "house" is read as the EDM genre even in "coffee house", and "mix" turns on the diversity penalty. I already had to remove "love" as a romantic-mood trigger because "I love jazz" was being read as a request for romance.
- **Negation is simple.** A negation word only affects a keyword within 3 words in the same clause. "Not only jazz" or "anything but rock and metal" can be misread.
- **English only**, and only the English vocabulary in the glossary.
- **Tiny catalog.** 18 songs, 13 of 15 genres with a single song. A "confidence" of 0.95 means "fits this small catalog well," not "this is what you would love." There is no blues, no k-pop and no "sad" cluster, so users who want those get a fallback and a warning.
- **Confidence is a heuristic, not a probability.** It blends three named signals with weights I chose; it has not been calibrated against real user satisfaction.
- **Carried over from VibeMatch 1.0:** exact-match genres (metal is as far from rock as from jazz), a loudness bias toward *Gym Hero*, and no learning from behavior.
- **No fairness evaluation across user groups.** I tested requests I invented, not requests from different kinds of listeners.

## 12. Could It Be Misused, and How Is That Prevented?

| Risk | Prevention in this system | Remaining gap |
|---|---|---|
| **Prompt-injection / instruction text** in a request ("ignore previous instructions...") | A pattern filter rejects it with a friendly message. More importantly, request text is only ever used for keyword lookup: it is never executed, never sent to a language model, never used to build a path or command, so there is nothing for an injection to take over | The pattern list is small and a rephrased attack would pass the filter. It would still be harmless for the same structural reason, but this would have to be redesigned if an LLM were added |
| **Oversized or junk input** (resource abuse) | 300-character limit, control-character stripping, "no letters" check | No rate limiting; this is a local tool |
| **Steering users with the glossary** (promoting particular songs or genres by editing keywords) | Glossaries are plain text in version control, so changes are reviewable; malformed sections are skipped and logged | Nothing stops a malicious maintainer; changes need code review |
| **Overtrusting the output** | Sources, assumptions and confidence are always shown; low confidence is labelled *needs_review* and the message says to check the results yourself | A user can still ignore the warning |
| **Privacy** | No network calls, no accounts. Requests are written to `logs/agent.log`, which is git-ignored | Logs contain whatever people type; a real deployment would need a retention policy and a rule against logging personal details |
| **Misuse as a "taste judge"** | Intended use (Section 2) says a low score means "does not match," not "bad music" | Cultural stereotypes in the glossary remain (Section 11) |

## 13. Testing Results and What Surprised Me

**Results.** 58/58 unit tests pass. The evaluation harness passes 20/20 cases: 12 normal requests, 8 guardrail cases. Average confidence on answered requests is 0.85 (0.91 for requests with status *ok*). The two requests for genres missing from the catalog (blues, k-pop) were correctly flagged for human review at confidence 0.45. All 20 cases return identical results on a second run. Turning the glossary off dropped "request understood" from 12/12 to 6/12 and "recommendation correct" from 12/12 to 4/12.

Caveat: I wrote the cases and expected answers myself and adjusted the system after seeing early failures, so this is a consistency check against my intent, not independent proof of quality.

**What surprised me.**

1. **Giving up made the confidence go up.** My first critic dropped the unmatched genre (k-pop, blues) and then scored the leftover match at 0.56 "ok," because with fewer requirements the top song fit almost perfectly. A metric that rewards dropping what the user asked for is dangerous, so a dropped requirement now caps confidence at 0.45.
2. **A one-line stemmer bug disabled negation.** The stemmer turned "nothing" into "noth," so "nothing too loud" was read as *wanting* loud music. The unit test for negation caught it; the retrieval looked fine on the happy path.
3. **One generic word hijacked a request.** "late-night" was a trigger for the night-driving document, so "late-night coding" returned synthwave instead of lofi. Realistic phrases found this; hand-picked test phrases would not have.
4. **The "repetition" check punished the user for asking for something.** Requesting lofi returns three lofi songs, which the first critic called "repetitive" and "fixed" by changing the ranking. Revisions now only trigger for repetition the user did not ask for, and only while the diversity penalty is off.
5. **One of my own tests was wrong.** The "too long" guardrail case was only 280 characters, under the 300 limit, so the system correctly accepted it and the test failed. I fixed the test, not the limit.

## 14. Human Evaluation

Automated checks confirm the system matches my expectations; a person should judge whether the answers are *good*. This table is a spot-check of the system's #1 pick for six requests (outputs copied from the evaluation run). **Reviewer: project author.**

| Test Input | Evaluation Criteria | System's #1 pick | Automated check | Human verdict |
|---|---|---|---|---|
| "late-night coding, nothing too loud, a bit dreamy" | Calm, low-energy, focus-friendly | Focus Flow (lofi, energy 0.40) | Pass | _to be completed by reviewer_ |
| "pump-up music for the gym" | Loud, high-energy | Gym Hero (pop, energy 0.93) | Pass | _to be completed by reviewer_ |
| "sad songs for a rainy day" | Sad / mellow, slow | Coffee Shop Stories (jazz, relaxed) | Pass | _to be completed by reviewer_ |
| "romantic dinner date" | Romantic, smooth | Velvet Hours (r&b, romantic) | Pass | _to be completed by reviewer_ |
| "I want some blues" | Honest about missing genre | Fallback list, flagged *needs_review* at 0.45 | Pass | _to be completed by reviewer_ |
| "no metal please, something calm" | No metal; calm | Moonlit Sonata Remix (classical, peaceful) | Pass | _to be completed by reviewer_ |

Reviewer note on the one I would watch: for "sad songs for a rainy day" the #1 pick is a *relaxed* jazz song rather than the *melancholic* folk song (*Autumn Letters*, #2), because "rainy" retrieved a jazz activity that outweighs the mood. A human may reasonably disagree with that ranking.

## 15. How I Collaborated with AI

I worked with Claude Code (inside my repo) using a **plan-first** workflow: I asked for a plan, approved or redirected it, then had Claude implement it. Claude wrote most of the code, tests and documentation drafts. I made the product decisions, and the tests and example runs were the check on its work.

**One suggestion I accepted.** I asked which planner design was best for this kind of project, and Claude recommended an **offline, rule-based planner** over a language-model planner, because anyone grading or running the project can reproduce it without an API key and identical answers make tests meaningful. I accepted it. It cost some language understanding (free-form phrasing fails), which I documented as a limitation.

**One suggestion I changed.** Claude's first plan proposed building all four optional stretch features, including a few-shot "specialization" one. I narrowed that: since the specialization stretch is optional and does not fit a rule-based system naturally, I told Claude to leave it out unless it was required. It was not, so it was skipped, and the other three stretches were built. Separately, Claude's first explanation of the assignment was too jargon-heavy for me; I asked for plain language and it re-explained the project with a restaurant analogy before any code was written.

**Where the AI was wrong, and how it was caught.** Claude's first implementation had real defects, all found by running the code rather than reading it: the stemmer bug that broke negation, the over-eager "late-night" trigger, a confidence score that rewarded dropping the user's genre, and a "repetition" check that fired on things the user had asked for (Section 13). Each fix has a regression test. Claude also initially wrote a test case that was itself wrong (the 280-character "too long" input), which is a reminder that AI-written tests need the same scrutiny as AI-written code.

**Honest limits of this reflection.** This section describes what happened in this session. The human-evaluation verdicts in Section 14 are still mine to fill in.
