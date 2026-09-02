docker run --rm     -v ~/.config/rclone:/config/rclone:ro     -v /tmp/whisper-sync:/workspace     -e WORKSPACE=/workspace     -e RCLONE_REMOTE=gdrive     -e DRIVE_INPUT=gdrive:whisper-sync/input     -e DRIVE_OUTPUT=gdrive:whisper-sync/output     whisper-sync


echo "=============================================================";
echo "sync/input directory";
ls -ltr /tmp/whisper-sync/sync/input/


echo "=============================================================";
echo "sync/output directory";
ls -ltr /tmp/whisper-sync/sync/output/