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

## Troubleshooting decode on PNG

Eclipsera automatically detects PNG images and adjusts analyzer behavior for best results.

### PNG vs JPEG analyzer compatibility

| Analyzer | PNG | JPEG | Notes |
|----------|-----|------|-------|
| **zsteg** | ✅ Yes | ❌ No | Primary tool for PNG LSB extraction |
| **steghide** | ❌ No | ✅ Yes | JPEG/BMP only; marked SKIPPED for PNG |
| **outguess** | ❌ No | ✅ Yes | JPEG-centric; marked SKIPPED for PNG |
| **binwalk** | ✅ Yes | ✅ Yes | File carving; "no extractor" is non-fatal |
| **exiftool** | ✅ Yes | ✅ Yes | Metadata extraction |
| **foremost** | ✅ Yes | ✅ Yes | File recovery |
| **strings** | ✅ Yes | ✅ Yes | ASCII string extraction |
| **decomposer** | ✅ Yes | ✅ Yes | Bit-plane decomposition |

### PNG-specific extraction
- **PNG images**: Use LSB (Least Significant Bit) planes with zsteg for extraction
  - Analyzers `steghide` and `outguess` are marked as SKIPPED (not ERROR) for PNG
  - The decoder automatically runs targeted zsteg extraction with multiple selectors:
    - `b1,r,lsb,xy` - LSB Red channel
    - `b1,r,msb,xy` - MSB Red channel
    - `b1,g,lsb,xy` - LSB Green channel
    - `b1,b,lsb,xy` - LSB Blue channel
    - `b1,rgb,lsb,xy` - LSB RGB combined
  - Recovered text appears in the "🔓 Recovered Text" section with diagnostics

### JPEG images
- **JPEG images**: `steghide` and `outguess` analyzers will run normally
  - Use these tools when working with JPEG carrier images
  - PNG-specific zsteg extraction is skipped for JPEG files

### Important notes
- **Avoid re-saving images** through tools that recompress them:
  - macOS Preview, Twitter, iMessage, screenshot tools often destroy LSB data
  - Always use the original downloaded PNG file for decryption
  - The encoder shows a warning: "Use the downloaded PNG directly"
- **Compression artifacts**: If the image has been compressed or converted, LSB steganography may be unrecoverable
- **File format detection**: The decoder uses magic bytes to detect PNG vs JPEG automatically
- **Twitter-safe mode**: The encoder's "Twitter-safe" option compresses to <900KB while preserving LSB capacity

### Visibility features
The decoder UI now includes:
- **🔓 Recovered Text**: Shows plaintext extracted from PNG LSB planes
- **🔬 Diagnostics**: Technical details (selector, byte length, hex preview)
- **📊 Analyzer Status**: Clean table showing ok/skipped/error counts
- **📋 Full analyzer logs**: Expandable section with detailed output

### Manual extraction
For debugging, you can manually extract text from a PNG using the helper script:
```sh
python scripts/extract_with_zsteg.py path/to/image.png
```

This will attempt extraction with multiple zsteg selectors and display any recovered text.

## Credits
- **Encoder**: original project from `eclipsera_blueprint/encoder`.
- **Decoder**: AperiSolve-inspired project from `eclipsera_blueprint/decoder`.
Both remain byte-identical under `vendor/`; consult their respective LICENSE/README files for attribution.
