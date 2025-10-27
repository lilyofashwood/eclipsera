# Eclipsera Encode→Decode Report

Generated: 2025-10-26T23:19:48Z
Overall status: ❌ FAIL
Successful runs: 2 / 3

| Cover | Variant | Message Found | Notes |
| --- | --- | --- | --- |
| sample_photos_to_encode_text_to_LSB/test_photo_1_unencrypted.png | overall | ✅ | binwalk: error; decomposer: ok; exiftool: error; foremost: error; steghide: error; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_1_unencrypted.png | channels_rgb | ✅ | binwalk: error; decomposer: ok; exiftool: error; foremost: error; steghide: error; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_1_unencrypted.png | rgb_zlib_deep | ⚠️ | binwalk: error; decomposer: ok; exiftool: error; foremost: error; outguess: error; steghide: error; strings: ok; zsteg: error |