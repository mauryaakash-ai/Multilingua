# Lip quality update

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.

The download output.mp4 was matched by SHA256 to server job 1364107fbec84529bdf167a587965469. Re-render: runs/lip-quality/improved.mp4. The original was preserved. Same Hindi audio, 134 frames, 5.36 seconds.

Generic voice configurations now opt into quality_mode: mouth. A local runner replaces only a dilated semantic lip region, with mild sharpening of the generated face before blending. This preserves more source beard and jaw texture than the broad jaw mask. Missing mouth segmentation fails explicitly. The upstream checkout is unchanged. The runner also preserves the CRF18 intermediate before upstream audio muxing re-encodes it; the adapter muxes it with stream-copy video.

Media stages now use CRF18. Webcam capture requests 1280x720 where supported; server preserves input size up to 1280 wide rather than forcing 640. Existing 640x480 captures cannot gain source detail from this change. Higher resolution may increase latency.

Validation: 30 regression tests passed; real GPU render, exact frame count/duration checks, five sampled frames visually inspected. Beard/jaw improvement is visible, but generated lips still look soft. This is not a validated improvement in synchronization accuracy or a complete fix for model reconstruction artifacts. Mouth-only blending is experimental and needs evaluation on varied poses, facial hair, and speakers. To restore original blending, remove quality_mode from the config.
