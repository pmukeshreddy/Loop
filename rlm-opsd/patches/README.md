# prime-rl OPSD patch

Apply with `make prime-opsd-patch` from `rlm-opsd/`. The source commit and
before/after file hashes are in `prime-rl-opsd.json`. The launcher validates
the patch before adding the source checkout to every process's Python path.
No installed distribution is overwritten.

These are modifications to Prime Intellect's prime-rl, licensed under Apache
2.0. Existing upstream copyright and license headers are retained. The patch
also changes the configuration package at the same commit. See
`../THIRD_PARTY_NOTICES.md` and the pinned checkout's `LICENSE`.

When updating the integration, regenerate the patch and both hashes from the
exact upstream commit, run the reconstruction test, and update the documented
source contracts in `../docs/VERIFIED_APIS.md`.
