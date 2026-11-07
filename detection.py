import re
import unicodedata
from better_profanity import profanity


profanity.load_censor_words()


# Symbols people use instead of letters to bypass the profanity filter
LEET = str.maketrans({
    "@": "a", "4": "a", "$": "s", "5": "s", "0": "o",
    "1": "i", "!": "i", "3": "e", "7": "t", "+": "t",
})

# Symbols that can stand for any vowel
Wild = "@*#$%&!+?"

# Single letters split by symbols or spaces
Spaces = re.compile(r"\b(?:[a-z][\W_]+){2,}[a-z]\b")

Edge = ".,;:!?\"'()[]{}<>"


def strip_accents(text):
    # Removes accents: shít -> shit
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def clean_edges(text):
    # Trims punctuation from the ends of each word: sh@t! -> sh@t
    return " ".join(t.strip(Edge) for t in text.split())


def joined_spaced(text):
    # Joins single letters: s.h.i.t -> shit
    return Spaces.sub(lambda m: re.sub(r"[\W_]+", "", m.group()), text)


def variants(text):
    base = clean_edges(strip_accents(text.lower()))

    forms = {base, base.translate(LEET)}
    for vowel in "aeiou":
        forms.add(base.translate(str.maketrans({c: vowel for c in Wild})))

    out = set()
    for f in forms:
        for c in (
            f,
            re.sub(r"(.)\1+", r"\1", f),
            re.sub(r"(.)\1{2,}", r"\1\1", f),
        ):
            out.add(c)
            out.add(joined_spaced(c))
    return out


def find_word(text):
    """Return the offending word, or None if the message is clean."""
    for v in variants(text):
        if profanity.contains_profanity(v):
            censored = profanity.censor(v, "*")
            for original, cens in zip(v.split(), censored.split()):
                if "*" in cens and "*" not in original:
                    return original.lower()
            return v[:50]
    return None