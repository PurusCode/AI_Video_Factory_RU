Kokoro ONNX benchmark fix: automatic splitting of text blocks for the 510-symbol IPA/style limit.

How to apply:
1. Extract this ZIP into the video-farm project root, keeping folder paths.
2. Overwrite tools\kokoro_onnx_benchmark.py when asked.
3. Run from PowerShell in the project root:
   .\.kokoro-venv\Scripts\python.exe -X utf8 .\tools\kokoro_onnx_benchmark.py --script data\tts_quality_benchmark_script.json --out output\kokoro-dima-benchmark --voice dima --threads 2

The script keeps normal blocks intact when they fit. When a block exceeds IPA length 510, it splits only at sentence/clause boundaries where possible, synthesizes chunks, and stitches them with 180 ms pauses. The manifest records chunk counts and IPA lengths. This is an evaluation-only script, not production integration.
