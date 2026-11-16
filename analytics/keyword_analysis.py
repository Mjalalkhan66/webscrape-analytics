"""Keyword extraction and rule-based categorisation (no external NLP dependencies)."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

import pandas as pd

STOPWORDS = frozenset("""
a about above after again against all also am an and any are aren't as at be because been before being below
between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each
few for from further get got had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself just let's like
made make many me more most much mustn't my myself new no nor not now of off often on once one only or other
ought our ours ourselves out over own same say said shan't she she'd she'll she's should shouldn't so some
such than that that's the their theirs them themselves then there there's these they they'd they'll they're
they've this those through to too under until up us use used using very was wasn't we we'd we'll we're we've
were weren't what what's when when's where where's which while who who's whom why why's will with won't would
wouldn't you you'd you'll you're you've your yours yourself yourselves via per etc however may might will
read more click share privacy policy cookies cookie terms home menu search login subscribe newsletter
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")

CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "Technology": frozenset("software ai artificial intelligence data cloud app apps digital internet cyber computer code programming developer startup tech technology device mobile network algorithm machine learning robot".split()),
    "Business & Finance": frozenset("market business company companies economy economic financial finance stock stocks investors investment bank revenue profit sales trade price prices growth industry startup funding inflation".split()),
    "Politics & Government": frozenset("government election political politics president minister parliament policy law legal court senate congress vote voters party public state federal military war diplomatic".split()),
    "Science & Health": frozenset("health medical medicine science research study scientists disease patients hospital climate environment energy space biology clinical treatment vaccine".split()),
    "Sports": frozenset("sport sports game games team teams player players season league match coach championship football cricket tournament score goal".split()),
    "Entertainment & Culture": frozenset("film movie music album artist actor show series culture festival book books author art theatre celebrity streaming".split()),
    "Education": frozenset("education school schools university students student learning teacher course courses college academic degree curriculum campus exam".split()),
    "Shopping & Products": frozenset("product products shop buy shipping order delivery cart discount deal review brand price sale collection available stock".split()),
    "Travel & Lifestyle": frozenset("travel hotel flight tourism destination food restaurant recipe fashion lifestyle home garden fitness wellness trip".split()),
}


def tokenize(text: str, min_len: int = 3) -> list[str]:
    """Lower-cased alphabetic tokens without stopwords."""
    tokens = (t.strip("'-").lower() for t in _TOKEN_RE.findall(text or ""))
    return [t for t in tokens if len(t) >= min_len and t not in STOPWORDS]


def top_keywords(texts: Iterable[str], top_n: int = 20, min_len: int = 3, bigrams: bool = False) -> pd.DataFrame:
    """Most frequent keywords (or bigrams) across ``texts`` as a DataFrame[keyword, count]."""
    counter: Counter[str] = Counter()
    for text in texts:
        tokens = tokenize(text, min_len)
        if bigrams:
            counter.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
        else:
            counter.update(tokens)
    rows = counter.most_common(top_n)
    return pd.DataFrame(rows, columns=["keyword", "count"])


def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    """Top keywords of a single document."""
    counts = Counter(tokenize(text, 4))
    return [w for w, _ in counts.most_common(top_n)]


def rule_based_category(text: str) -> tuple[str, int]:
    """Assign the best-matching category; ``("General / Other", 0)`` if evidence is weak."""
    tokens = Counter(tokenize(text, 2))
    best, best_score = "General / Other", 0
    for category, words in CATEGORY_KEYWORDS.items():
        score = sum(tokens[w] for w in words if w in tokens)
        if score > best_score:
            best, best_score = category, score
    if best_score < 2:
        return "General / Other", best_score
    return best, best_score


def extractive_summary(text: str, max_sentences: int = 3) -> str:
    """Frequency-based extractive summary (the non-AI fallback)."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if len(s.strip()) > 30]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    freq = Counter(tokenize(text))
    scored = []
    for i, sentence in enumerate(sentences):
        words = tokenize(sentence)
        score = sum(freq[w] for w in words) / (len(words) ** 0.5 + 1)
        scored.append((score, i, sentence))
    top = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda t: t[1])
    return " ".join(s for _, _, s in top)
