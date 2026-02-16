#!/usr/bin/env python3
"""Quick test: why are user messages all classified as neutral?"""
import re

POSITIVE_WORDS = frozenset({
    "good", "great", "excellent", "awesome", "amazing", "love", "happy",
    "thanks", "perfect", "wonderful", "fantastic", "yes", "correct",
    "right", "helpful", "clear", "understood", "understands", "nice",
    "brilliant", "superb", "beautiful", "glad", "pleased", "thrilled",
    "better", "best", "clean", "cleaner", "improved", "enjoy", "enjoyed",
    "like", "liked", "smooth", "prefer", "comfortable", "easy", "easier",
    "fine", "well", "solid", "neat", "cool", "impressive", "reliable",
    "fast", "quick", "efficient", "elegant", "smart", "working", "works",
    "sweet", "okay", "ok", "satisfied", "safe", "stable", "ready",
    "fun", "dear", "hope", "welcome", "promise", "free",
})

NEGATIVE_WORDS = frozenset({
    "bad", "terrible", "awful", "hate", "angry", "frustrated", "confused",
    "wrong", "error", "fail", "failed", "stupid", "useless", "no", "not",
    "problem", "issue", "broken", "slow", "disappointed", "annoying",
    "boring", "ugly", "horrible", "worst", "bugs", "crash", "stuck",
    "worse", "painful", "messy", "unclear", "hard", "difficult", "missing",
    "lost", "confusing", "annoyed", "tired", "worried", "afraid", "scary",
    "impossible", "unreliable", "unstable", "laggy", "complicated", "sucks",
})

samples = [
    "have a nice night my dear familiar",
    "i hope you will be happy you have now sentiment",
    "have fun",
    "Hello my dear familiar",
    "You said bug fix about memory compression",
    "quantic",
    "quantum",
    "ok we update your models list",
    "Ok i did all the patches",
    "Keep on kimi but rationnate your token usage",
]

for t in samples:
    words = re.findall(r"\b\w+\b", t.lower())
    total = max(len(words), 1)
    pos = [w for w in words if w in POSITIVE_WORDS]
    neg = [w for w in words if w in NEGATIVE_WORDS]
    valence = max(-1.0, min(1.0, (len(pos) - len(neg)) / total * 3))
    label = "POSITIVE" if valence >= 0.25 else "NEGATIVE" if valence <= -0.25 else "NEUTRAL"
    print(f'"{t[:55]}"')
    print(f'  pos={pos} neg={neg} valence={valence:.3f} => {label}')
    print()
