# Eclipsera

Eclipsera wraps the original encoder and decoder projects into a single Streamlit application with an "upload first" flow. The vendor projects live untouched under `vendor/` and are surfaced via thin adapters so their behaviour stays intact.

## Features
- Single Streamlit interface with **Encrypt** / **Decrypt** modes unlocked after an image is uploaded.
- Encoder adapter preserves Twitter-safe compression, per-channel controls, and optional zlib embedding.
- Decoder adapter reuses AperiSolve analyzers, collecting plane previews, CLI artefacts, and textual findings.
- Automated encode→decode smoke tests using the fixtures under `encoding_decoding_tests/`.
- Dockerfile suitable for Render deployment with all system tools installed (binwalk, steghide, etc.).

## Repository layout
```
app/
  adapters/      # Glue code into vendor projects
  ui/            # Streamlit UI components & styles
  app.py         # Streamlit entrypoint
vendor/
  encoder/       # Original encoder project (read-only)
  decoder/       # Original decoder project (read-only)
scripts/
  check_vendor_integrity.py
  run_roundtrip.py
encoding_decoding_tests/
  sample_photos_to_encode_text_to_LSB/
  sample_encrypted_photos_LSB_text/
  LSB_text_output_within_encrypted_photos/
  results/
notes/
  discovery.md
  debug-log.md
```

## Getting started
1. Install Python dependencies (Python 3.11 recommended):
   ```sh
   python3 -m pip install -r requirements.txt
   ```
2. (Optional) Install system tools if you want full decoder coverage locally. On Debian/Ubuntu:
   ```sh
   sudo apt-get update
   sudo xargs -a requirements-system.txt apt-get install -y
   sudo gem install zsteg
   ```
3. Run the Streamlit app:
   ```sh
   streamlit run app/main.py
   ```

The UI expects you to upload a carrier image first, then choose **Encrypt** or **Decrypt**. Results stay on screen after each action for convenient comparison.

## Automated encode→decode checks
The script below exercises the encoder/decoder pipeline using the fixture directories specified in the brief. It writes encoded images, decoder outputs, and reports into those folders.
```sh
python scripts/run_roundtrip.py
```
Outputs:
- Encoded images in `encoding_decoding_tests/sample_encrypted_photos_LSB_text/`
- Decoder dumps (planes, artefacts, summary) in `encoding_decoding_tests/LSB_text_output_within_encrypted_photos/`
- `encoding_decoding_tests/results/report.{json,md}` summarising each run

Two of the baseline scenarios recover the golden message directly. The zlib scenario writes valid payload bits but the vendor terminator strategy truncates the compressed stream; it is recorded as a soft failure in the report.

## CI safeguards
- `scripts/check_vendor_integrity.py` recomputes SHA-256 hashes for every vendored file and fails if they deviate from `vendor/MANIFEST.sha256`.
- `.gitattributes` marks `vendor/**` as vendored to avoid false-positive diffs.
- `.github/workflows/ci.yml` installs dependencies, runs the vendor integrity check, and executes the smoke tests on every push/PR.
- `githooks/pre-commit` blocks staged changes underneath `vendor/` unless you are refreshing the manifest.

## Docker & deployment
Build locally:
```sh
docker build -t eclipsera .
```
The container runs `streamlit run app/main.py` on `$PORT` (default 8080). All decoder CLI tools from `requirements-system.txt` are installed, including `zsteg` via RubyGems.

Render deployment checklist:
1. Push this repository to GitHub (e.g. `Eclipsera`).
2. In Render, create a new **Web Service**, choose *Docker* environment, and point it at the repo.
3. Use the provided `Dockerfile`; no additional build commands are needed.
4. After deployment, record the public URL in `notes/deployed-url.txt`.

_(Deployment requires platform credentials; capture the final URL after verifying an end-to-end encode/decode round trip on the hosted instance.)_

## Credits
- **Encoder**: original project from `eclipsera_blueprint/encoder`.
- **Decoder**: AperiSolve-inspired project from `eclipsera_blueprint/decoder`.
Both remain byte-identical under `vendor/`; consult their respective LICENSE/README files for attribution.
