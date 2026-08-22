# CIE Interoperability v2 Parent Rollback

1. Close the child and parent draft PRs or revert only their candidate commits through governed authority.
2. Remove only `ct.framework-agent.cie` and `ct.subagent.cie-interoperability` from the two CIE CHLOM capability allowlists; preserve every pre-existing and concurrent identity.
3. Remove only the candidate metadata keys listed in the SQL rollback block; preserve package history, digests and protected assets.
4. Keep CIE operational=false, voting=false, live private dispatch=false and parent certification pending.
5. Keep Convergent Ecosystem `RESEARCH_CANDIDATE_ONLY`.
6. Preserve all issue, PR, Drive, THIVEBASE and CI evidence.

Reopen on parent/child head drift, contract/capability digest drift, OIDC or Agent D state change, rights classification change, specialist block, failed negative control or unauthorized activation/commercialization attempt.
