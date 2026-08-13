"""
sweep.py — step 1 of the migration recipe, done across the WHOLE package.

MIGRATION-2.0.md §19 demonstrates the inventory by running app.py and counting
5 warnings. That is a demonstration, not an inventory: app.py only *queries*, so
it never builds an object graph, so it never triggers the cascade_backrefs
breakage (§17) — the most dangerous item in this repo. A one-file sweep found
five things and missed the worst one.

This runs the sweep the way the recipe actually means it: every module, each in
its own subprocess (the env var and the -W filter both have to be set before
SQLAlchemy is imported, so they cannot be toggled in-process).

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.sweep

NOTE: seed.py is included and rewrites issues.db. That is deterministic — its
RANDOM_SEED is fixed — so the file is byte-identical afterwards, but it does
mean this is not a read-only command the way `-m ... app` alone is.
"""

import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

PACKAGE = "experiments.sqlalchemy_1_4_vs_2_0"

# check.py is included precisely because it looks like it has nothing to say:
# it only imports the models and configures mappers, and that alone is enough
# to surface the declarative_base import.
MODULES = ["check", "app", "states", "explore", "migration", "seed"]

WARNING_RE = re.compile(r"\b(RemovedIn20Warning|MovedIn20Warning|LegacyAPIWarning)\b: (.+)")

# The message text carries object and relationship names that vary per row;
# collapse them so 1013 occurrences of one problem read as one problem.
NORMALISERS = [
    (re.compile(r'"[A-Za-z_]+" object'), '"X" object'),
    (re.compile(r'relationship "[^"]*"'), 'relationship "X"'),
]


def normalise(message):
    text = message.strip()
    for pattern, replacement in NORMALISERS:
        text = pattern.sub(replacement, text)
    # Drop the trailing "(Background on ... )" links; they are noise here.
    text = re.split(r"\s*\(Background on", text)[0]
    return text[:88]


def sweep_module(name):
    """Run one module under the 2.0 warning flags and return its warnings."""
    env = {**os.environ, "SQLALCHEMY_WARN_20": "1"}
    proc = subprocess.run(
        [sys.executable, "-W", "always::DeprecationWarning", "-m", f"{PACKAGE}.{name}"],
        capture_output=True, text=True, env=env,
    )
    found = []
    for line in proc.stderr.splitlines():
        match = WARNING_RE.search(line)
        if match:
            found.append((match.group(1), normalise(match.group(2))))
    return proc.returncode, found


print("=" * 78)
print("The inventory, run across every module — not just app.py")
print("=" * 78)
print()

per_module = {}
distinct = defaultdict(Counter)
for module in MODULES:
    code, found = sweep_module(module)
    per_module[module] = Counter(cls for cls, _ in found)
    for cls, message in found:
        distinct[cls][message] += 1
    if code != 0:
        print(f"  !! {module} exited {code} — its inventory may be incomplete")

classes = ["RemovedIn20Warning", "MovedIn20Warning", "LegacyAPIWarning"]
print(f"  {'module':<12}{'Removed':>9}{'Moved':>8}{'Legacy':>8}")
print(f"  {'-' * 12}{'-' * 9}{'-' * 8}{'-' * 8}")
for module in MODULES:
    counts = per_module[module]
    row = "".join(f"{counts.get(c, 0):>{w}}" for c, w in zip(classes, (9, 8, 8)))
    print(f"  {module + '.py':<12}{row}")
totals = Counter()
for counts in per_module.values():
    totals.update(counts)
print(f"  {'-' * 12}{'-' * 9}{'-' * 8}{'-' * 8}")
print(f"  {'TOTAL':<12}" + "".join(f"{totals.get(c, 0):>{w}}" for c, w in zip(classes, (9, 8, 8))))

print()
print("  app.py alone reports "
      f"{sum(per_module['app'].values())} of the {sum(totals.values())} occurrences above.")
print()

print("=" * 78)
print("Occurrences are not problems — the same fix repeated is one entry")
print("=" * 78)
for cls in classes:
    messages = distinct[cls]
    if not messages:
        continue
    print()
    print(f"  {cls}  —  {len(messages)} distinct, {sum(messages.values())} occurrences")
    for message, count in messages.most_common():
        print(f"    {count:>5}x  {message}")

print()
print("=" * 78)
print("What to do with this")
print("=" * 78)
print("  RemovedIn20Warning is the only breakage tier, so only its DISTINCT")
print("  rows above become deliverables/BREAKAGES.md entries. Note how badly occurrence")
print("  counts would mislead you about the size of the job: the cascade")
print("  fires once per attached object, so its count tracks how much data")
print("  the script builds, not how much code you have to change.")
print()
print("  Filter by EXACT class name, never isinstance() — MovedIn20Warning")
print("  is a SUBCLASS of RemovedIn20Warning, so isinstance() would fold the")
print("  import move into the breakage list.")
