# Doom Desktop Assistant

Doom is a Windows desktop assistant with Gemini-powered chat and voice,
computer actions, and a Windows desktop interface. Chat and voice requests are
sent to Google's Gemini service, so an internet connection and Gemini API key
are required. Local files and desktop actions run on the user's computer.

This repository is the Doom project; it does not claim to be an official
Microsoft, Marvel, or Bethesda product, and it is not affiliated with those
organizations or brands.

## Run a Windows release

After a Windows release has been published, download its ZIP from GitHub,
extract it, and run `Doom-Setup.exe`.
The installer creates a Desktop shortcut. On first launch, enter a Gemini API
key in Doom's setup screen. Doom does not install Ollama or download a local
language or speech model.

Spoken replies use the Windows speech voices installed on that PC. Voice input
is sent to Gemini for recognition and response. Web, browser, and other
network actions use the internet only when requested. Optional integrations
that require their own accounts are not preconfigured in the public release.

## Source development

Use Python 3.11 on Windows, install the dependencies from `requirements.txt`,
and run `python main.py`. Enter a Gemini API key on first launch.

The included GitHub Actions workflow builds the Windows installer. Push a
version tag such as `v1.0.0` to publish `Doom-Setup.exe` and
`Doom-Windows-Setup.zip` as a GitHub Release. A manual workflow run produces a
downloadable build artifact. The installer creates a Desktop shortcut and
does not require administrator rights.

## Privacy and safety

- Conversation and voice input are sent to Gemini; do not send information you
  do not want processed by Google's service.
- The public build contains no developer API keys or personal memory.
- Doom asks for confirmation for actions classified as sensitive by its safety
  gate.

## Licensing

Project source is provided under the MIT License in [LICENSE](./LICENSE).
A bundled notice for attribution and third-party dependency awareness is also
included in [NOTICE.txt](./NOTICE.txt). For future-proof compliance and
redistribution review, see the additional licensing pack in [LICENSES/](./LICENSES/).

Third-party software, model weights, bundled assets, Google Gemini services,
Windows platform components, and any runtime dependencies remain subject to
their respective licenses and terms. Review those terms before redistribution
or commercial use.
