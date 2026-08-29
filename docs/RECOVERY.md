# InWork disaster recovery

## Goal
Keep the project recoverable without depending on one hosting or source-control provider.

## Rules
1. GitHub is a source mirror, not the only copy.
2. Keep a second Git remote under the owner's control (for example a self-hosted Git service or a separate provider).
3. Keep periodic encrypted archives of the repository and deployment configuration.
4. Never store OAuth secrets, service-role keys, signing keys, or API keys in Git.
5. Production access must use named accounts, MFA, short-lived credentials, and documented recovery codes.
6. Recovery credentials must be stored outside the repository in a password manager or offline encrypted vault.

## Recovery test
At least once per release, restore the project from the secondary copy into a clean environment and run the smoke tests before declaring the release recoverable.

## Important
This is legitimate business continuity. It deliberately avoids hidden accounts, backdoors, credential harvesting, or mechanisms intended to bypass a provider suspension.
