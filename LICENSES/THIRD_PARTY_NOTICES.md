# Third-party component notice

This document is a practical record for third-party and service dependencies that
Doom may rely on during development, packaging, or release. It is intentionally
kept durable so it can be expanded in the future as new dependencies are added.

## Project-level license

- Project source code: MIT License (`LICENSE` in the repository root)
- Project notice: `NOTICE.txt`

## Dependency groups to monitor

### Python package dependencies
The project uses packages such as:

- PyQt6
- sounddevice
- numpy
- google-genai
- fastapi and uvicorn
- requests and beautifulsoup4
- playwright
- pyautogui and pygetwindow
- pillow, opencv-python, mediapipe, mss
- psutil, send2trash, youtube-transcript-api, python-pptx, openpyxl
- google-api-python-client and google-auth-oauthlib
- tinytuya
- comtypes, pycaw, win10toast, pywinauto, pywin32, wmi on Windows

Each package is distributed under its own license terms and may require vendor
notice or attribution when bundled with a build or redistributed source package.

### Platform and OS runtime dependencies
Doom may rely on components such as:

- Windows speech and accessibility APIs
- PyQt6 / Qt runtime components
- local audio system libraries and platform-level tools
- browser automation or system APIs exposed by the OS

These are subject to the terms of the platform vendor and any accompanying SDK or
runtime licenses.

### Cloud and web services
Doom integrates with Google Gemini services and may rely on Google APIs and
related platform terms. Use of those services is governed by the service
provider's separate terms, data-processing rules, and any required notices.

### Bundled assets or optional tools
If future builds add packaged fonts, icons, sound files, browser drivers,
third-party binaries, or SDK assets, each item should be recorded here with:

- component name
- source or vendor
- license name
- short summary of obligations
- link or path to the original license text

## Future policy

When new external components are added, add a short entry below in this format:

- Name: <component>
- Purpose: <what it is used for>
- License: <license family or exact license>
- Source: <package, vendor, or service>
- Notes: <distribution / attribution / legal obligations>

## Example entries

- Name: PyQt6
- Purpose: GUI framework
- License: Qt licensing terms / LGPL compatibility terms as applicable
- Source: Riverbank Computing / Qt project
- Notes: Confirm the exact license terms for the chosen distribution and packaging model.

- Name: Google Gemini
- Purpose: AI chat and speech processing
- License: Google service terms and API terms
- Source: Google
- Notes: Review the current Google terms and any customer/usage restrictions before redistribution or business deployment.

## Distribution reminder

When releasing a packaged app, ensure that all required third-party notices,
licenses, and service terms remain with the distribution package and are not
omitted due to packaging simplification.
