# Telegram video attachments

Route outgoing MP4 video attachments through sendVideo with the original caption and reply reference. Share bounded 16 MB payload and H.264/AAC codec validation with the existing WhatsApp path. Invalid uploads fail locally before provider submission. Existing retry classification and operation identity remain unchanged.

Validation: 46 gateway tests passed; one existing real FFmpeg test skipped because FFmpeg/ffprobe are absent on the validation host. Video provider upload and codec results use mocked transport/probe fixtures. The worker host must have its existing FFmpeg dependency installed for video/audio processing. No gateway deployment or restart was performed.
