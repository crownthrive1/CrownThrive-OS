# PentaBooks automation scripts

`rotation_custody_guard.py` emits a deterministic, public-safe cycle evidence artifact. It intentionally does not manufacture Drive, ThriveBase, commerce, entitlement, or release success.

Provider adapters may be added only when they:

1. read secrets from approved runtime aliases;
2. bind an exact rotation, SKU, edition, and hash;
3. perform the provider mutation or read;
4. read the result back from the provider;
5. append immutable evidence;
6. update projections only after the evidence write succeeds;
7. fail closed without damaging unrelated accepted artifacts.
