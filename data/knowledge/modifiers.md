# Modifier glossary

Modifiers nudge the profile instead of setting it. `energy_delta` is added to
the current target energy. `negatable: yes` means a negation flips the effect,
so "nothing too loud" lowers energy rather than raising it.

## Louder
kind: modifier
keywords: loud, louder, energetic, high energy, high-energy, powerful, banging
energy_delta: 0.20
negatable: yes

## Quieter
kind: modifier
keywords: quiet, quieter, soft, gentle, low-key, low energy, low-energy, subtle
energy_delta: -0.20
negatable: yes

## Upbeat
kind: modifier
keywords: upbeat, bouncy, lively, peppy
energy_delta: 0.15
negatable: yes

## Acoustic
kind: modifier
keywords: acoustic, unplugged, organic
acoustic: yes
negatable: yes

## Electronic sound
kind: modifier
keywords: electronic sound, synthetic, produced
acoustic: no
negatable: yes

## Instrumental
kind: modifier
keywords: instrumental, instrumentals, no words
instrumental: yes
negatable: yes

## Vocals
kind: modifier
keywords: vocals, lyrics, singing, singer, sing along, sing-along
instrumental: no
negatable: yes

## Decade 1980s
kind: modifier
keywords: 80s, eighties, 1980s
decade: 1980

## Decade 1990s
kind: modifier
keywords: 90s, nineties, 1990s
decade: 1990

## Decade 2000s
kind: modifier
keywords: 2000s, y2k, noughties
decade: 2000

## Decade 2010s
kind: modifier
keywords: 2010s
decade: 2010

## Variety
kind: modifier
keywords: variety, mix, mixed, diverse, different artists, surprise me
diverse: yes
