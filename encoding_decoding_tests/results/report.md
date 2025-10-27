# Eclipsera Encode→Decode Report

Generated: 2025-10-27T03:07:06Z
Overall status: ❌ FAIL
Successful runs: 4 / 6

| Cover | Variant | Message Found | Recovered Text | Notes |
| --- | --- | --- | --- | --- |
| sample_photos_to_encode_text_to_LSB/test_photo_1_unencrypted.png | overall | ✅ | Eclipsera golden vector v1: hello, moon | binwalk: error; decomposer: ok; exiftool: error; foremost: error; steghide: skipped; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_1_unencrypted.png | channels_rgb | ✅ | Eclipsera golden vector v1: hello, moon | binwalk: error; decomposer: ok; exiftool: error; foremost: error; steghide: skipped; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_1_unencrypted.png | rgb_zlib_deep | ⚠️ | (none) | binwalk: error; decomposer: ok; exiftool: error; foremost: error; outguess: skipped; steghide: skipped; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_2.png | overall | ✅ | Eclipsera golden vector v1: hello, moon | binwalk: error; decomposer: ok; exiftool: error; foremost: error; steghide: skipped; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_2.png | channels_rgb | ✅ | Eclipsera golden vector v1: hello, moon | binwalk: error; decomposer: ok; exiftool: error; foremost: error; steghide: skipped; strings: ok; zsteg: error |
| sample_photos_to_encode_text_to_LSB/test_photo_2.png | rgb_zlib_deep | ⚠️ | (none) | binwalk: error; decomposer: ok; exiftool: error; foremost: error; outguess: skipped; steghide: skipped; strings: ok; zsteg: error |