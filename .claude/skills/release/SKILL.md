---
name: release
description: Bump version, commit, tag, build, publish, and push a new release of the tslocalapi libraries. Use when the user says "release", "publish", or "bump version".
disable-model-invocation: true
argument-hint: <npm-otp>
---

# Release tslocalapi

Determine the next version by reading the current version from `Cargo.toml` and incrementing the patch number.

## Steps

1. **Bump version** in all five files:
   - `Cargo.toml` — `version = "X.Y.Z"`
   - `package.json` — `"version": "X.Y.Z"`
   - `pyproject.toml` — `version = "X.Y.Z"`
   - `python/src/tslocalapi/__init__.py` — `__version__ = "X.Y.Z"`
   - `README.md` — `tslocalapi = "X.Y.Z"` in the Rust install example

2. **Commit**: `git commit -am "Bump version to X.Y.Z"`

3. **Tag**: `git tag vX.Y.Z`

4. **Build TypeScript**: `npm run build`

5. **Publish all three** (in parallel):
   ```sh
   cargo publish
   uv build && uv publish
   npm publish --otp=<otp from $0>
   ```

6. **Push**: `git push && git push --tags`
