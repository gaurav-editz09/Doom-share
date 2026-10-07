# Licensing and third-party notices

This directory is a future-proof licensing pack for Doom. Keep it alongside the
project's main `LICENSE` file and `NOTICE.txt` in any source archive,
redistribution, or packaged build.

## Included records

- `LICENSE` in the project root remains the primary project license for this
  codebase.
- `NOTICE.txt` in the project root provides a concise project-level notice.
- `THIRD_PARTY_NOTICES.md` documents the main external dependency categories and
  where to record additional licensing obligations.

## Why this exists

Doom depends on multiple external components, including:

- Python libraries and runtime dependencies from `requirements.txt`
- Google Gemini and related API services
- Windows platform APIs and speech/desktop components
- bundled or optional assets used by the UI, browser automation, or media stack

Each external component may have its own copyright, license, terms of use, or
attribution requirement. A project-level MIT license does not replace those
third-party terms.

## Distribution checklist

Before releasing a packaged build or distributing the source code, confirm that:

1. The project root `LICENSE` file is included.
2. The root `NOTICE.txt` file is included.
3. This `LICENSES/` directory is included when shipping source or binary builds.
4. Any packaged dependency or SDK vendor terms are preserved as required.
5. If a bundled third-party binary, asset, font, or SDK is added later, its own
   license text is added here or linked from `THIRD_PARTY_NOTICES.md`.

## Important legal note

This repository is not a substitute for legal review. License obligations may
change as dependencies are added, removed, or upgraded. If a future release will
be distributed commercially, publicly, or with bundled third-party binaries,
review all vendor terms before shipping.
