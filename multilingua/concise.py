"""Narrow Hindi grammatical contractions, never truncation or fact deletion."""


def compact_hindi(text):
    # Shared progressive ending remains in the second coordinated verb.
    # Deliberately avoid a generic 'delete words until it fits' algorithm.
    return text.replace("संपर्क कर रहे हैं और उन्हें", "संपर्क कर उन्हें")
