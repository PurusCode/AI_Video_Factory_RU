AI VIDEO FACTORY RU — STAGE 3 INSTALLER

1. Extract the complete ZIP directly into the project root:
   D:\my_projects\AI_Video_Factory_RU\video-farm
   (the folder containing pyproject.toml and src\video_farm).
   Allow Windows to replace install_stage3.ps1 and the stage3 folder if asked.

2. Open PowerShell in that project root and run:
   .\install_stage3.ps1

The PowerShell file is only a launcher. Matching, backups, installation, syntax
checks and tests are handled by the included Python installer. It uses
.venv\Scripts\python.exe when present.

Changed files are backed up under backups\discovery-stage3-<timestamp>.
If a check fails, the original files are restored automatically. The installer
does not edit .env, virtual environments, model caches or discovery.json, and
does not call the YouTube API.

After successful installation, run:
   .\.venv\Scripts\python.exe -m video_farm.cli discover-analyze

Expected outputs: output\discovery\topics.json and topics.md
