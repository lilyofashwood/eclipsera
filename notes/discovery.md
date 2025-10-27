# Discovery Notes — Eclipsera Integration

## Encoder (Original)
- **Location**: `../eclipsera_blueprint/encoder`
- **Primary entrypoint**: `app.py` (Streamlit app embedding text via LSB; supports Twitter-safe mode, per-channel toggles, zlib, RGBA handling)
- **Python deps**: from `requirements.txt` → `streamlit`, `pillow`
- **Assets**: includes reference images `stegg.png`, `stegg(1).png`; MIT License present.
- **Notes**: Pure Streamlit workflow; no external CLI tools. Will be vendored without modification.

## Decoder (Original)
- **Location**: `../eclipsera_blueprint/decoder/aperisolve`
- **Primary entrypoints**:
  - `app.py` (Flask front-end), `wsgi.py` (Gunicorn entry), `workers.py` (RQ workers)
  - Analyzers coordinate through Redis-backed jobs
- **Python deps**: `Flask`, `Flask-SQLAlchemy`, `numpy`, `redis`, `rq`, `psycopg2-binary`, `types-Flask-SQLAlchemy`, `sqlalchemy-stubs`, `Pillow`, `gunicorn`
- **System/CLI deps** (from Dockerfile & analyzer implementations):
  - `zip`, `p7zip-full`, `binwalk`, `foremost`, `exiftool`, `steghide`, `ruby` (for `zsteg` gem), `binutils`, `outguess`, `pngcheck`, `redis-server`
  - Analyzer templates also reference `myanalyzer` but not enabled by default (active analyzers per `config.py`: `binwalk`, `foremost`, `steghide`, `zsteg`)
- **Assets**: `templates/`, `static/`, example submissions under `examples/`
- **Notes**: Designed for web + background processing; we will wrap analyzers via adapters, reusing CLI calls.

## Decoder Upload Fix
- `static/js/aperisolve.js` already includes the guard: uploader handlers call `preventDefault()/stopPropagation()` and return early when no file is selected. No additional patch required at this stage.

## Next Focus
- Scaffold unified repo under `eclipsera_repo/` while keeping `encoding_decoding_tests/` untouched.
