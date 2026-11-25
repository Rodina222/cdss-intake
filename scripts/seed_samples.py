"""Add the 31 typed sample dialogues as cases (sample-d01 ...) and copy the answer keys to data/gold.
The keys d01.json ... also match your own recordings if you name them d01.m4a ... d31.m4a."""
import _path  # noqa: F401
from cdss import samples

print("created:", samples.seed_samples())
