"""Auto-enhance: an automated self-improvement loop (التحسين التلقائي).

The model talks to itself — generate a topic, answer it, score the answer,
self-correct until it passes a quality gate, curate the passing turns, train a
QLoRA run, activate the new version, and repeat for N generations.
"""
