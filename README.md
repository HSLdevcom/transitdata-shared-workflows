# transitdata-shared-workflows

Control and modify the GitHub Actions workflows of [Transitdata](https://github.com/HSLdevcom/transitdata) in one place.

## TODO

- Use branch `main` with tagged versions
- Possibly create dummy test Java and TypeScript packages to test the workflow scripts. Or use `@main` for testing in one client repository before upgrading the version here.
- Secure

  - If any inputs or vars are given by the user, sanitize them carefully!

    - For example, only use inputs via `env`. E.g.

      ```yaml
      - name: Run linter
        run: npx eslint "${TARGET}"
        env:
          TARGET: ${{ inputs.target-directory }}
      ```

      - That way `TARGET` is quoted as a single string.

  - Use only trusted sources of actions or audit every line of code yourself
  - Pin all used actions external to this repository
  - Add strict branch protection / ruleset rules

- Add transitdata-common reusable workflow
- Add transitdata Java client reusable workflow
- Add transitdata TypeScript client reusable workflow
- Refactor the same parts into composite actions if useful
- Write documentation on how to use:
  - Recommend pinning with SHA1 and a version comment, e.g.
    immutable GitHub Actions (e.g. `uses: actions/checkout@a5ac7e51b41094c92402da3b24376905380afc29 # v4.1.6`)
  - Recommend using Dependabot
- Enable Dependabot on this repository
- Enable CodeQL, secret scanning and other static analysis and linting on this repository.
- Possibly no auto-merge for this repository
