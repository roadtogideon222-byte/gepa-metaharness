# Security Policy

## Reporting

If you find a security issue in `metaharness`, report it privately to the maintainer instead of opening a public issue.

Include:

- affected version or commit
- impact
- reproduction steps
- any suggested mitigation

## Scope

The most relevant areas are:

- shell command execution paths
- filesystem mutation paths
- provider backend integrations
- benchmark scripts that invoke local tooling
