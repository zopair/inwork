# InWork V2 architecture

## Product layers

- **Mobile-first PWA:** the current Arabic/RTL experience remains the fastest family-testing surface.
- **Domain core:** deterministic, explainable opportunity matching; language is a hard gate.
- **API:** FastAPI boundary for matching and opportunity feeds.
- **Auth:** Google OAuth should be implemented through a managed identity layer (Supabase Auth is a good fit) rather than hand-rolling OAuth.
- **Data:** PostgreSQL with row-level security once a real backend is connected.
- **AI layer:** optional enrichment only — extract skills from free speech/text, normalize skills, and suggest courses. AI must not silently invent qualifications or override hard constraints.
- **Feeds:** adapters for local jobs, freelance marketplaces, international sources, and manually curated opportunities. Each result keeps provenance internally even when the public UI hides it.
- **Admin:** protected demo/persona tooling, separated from normal user routes.

## Matching philosophy

1. Hard constraints first: language and explicit user restrictions.
2. Soft ranking second: skills, work mode, experience, interests, and location.
3. Every recommendation carries human-readable reasons.
4. No fake confidence percentages.
5. When results are thin, recommend concrete learning paths instead of showing a dead end.

## Release path

Prototype -> family beta -> real opportunity feeds -> authenticated beta -> production.

Do not connect real user data or real OAuth secrets until the legal text, privacy policy, consent versioning, and deletion/export flows are verified.
