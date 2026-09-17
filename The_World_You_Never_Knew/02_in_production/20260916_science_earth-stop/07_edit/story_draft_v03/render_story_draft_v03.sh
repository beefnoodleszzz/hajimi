#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EDIT="$ROOT/07_edit/story_draft_v03"
FLOW="$EDIT/flow_segments"
ASSETS="$ROOT/05_visuals/generated_v03_story"
ASSETS_V04="$ROOT/05_visuals/generated_v04_story"
GRAPHICS="$EDIT/graphics"
VOICE="$ROOT/04_voice/story_v02/voiceover_story_v02.wav"
WORK="$EDIT/render_work"
CAP_DIR="$WORK/subtitles_right_bottom"
FINAL="$EDIT/earth_stop_story_v03_review.mp4"
FONT="/System/Library/Fonts/Supplemental/Arial.ttf"

mkdir -p "$WORK" "$CAP_DIR"

make_subtitle() {
  local output="$1"
  local text="$2"
  magick -size 1080x1920 xc:none -gravity SouthEast \
    -font "$FONT" -pointsize 40 -fill '#F3FAFF' -stroke '#07111f' -strokewidth 2 \
    -annotate +70+110 "$text" -depth 8 "$output"
}

encode_video() {
  local input="$1"
  local offset="$2"
  local duration="$3"
  local output="$4"
  ffmpeg -hide_banner -loglevel error -y \
    -ss "$offset" -i "$input" -t "$duration" \
    -vf "scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p" \
    -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$output"
}

make_subtitle "$CAP_DIR/01.png" $'Imagine the ground under your feet\nstopping for exactly one second.'
make_subtitle "$CAP_DIR/02.png" $'At the equator, you are already moving east\nat about 465 meters per second.'
make_subtitle "$CAP_DIR/03.png" 'The road stops, but your body keeps going.'
make_subtitle "$CAP_DIR/04.png" $'In that single second, you move nearly 465 meters\nrelative to the ground,'
make_subtitle "$CAP_DIR/05.png" 'about four football fields, without taking a step.'
make_subtitle "$CAP_DIR/06.png" 'Gravity still holds you down. The danger is sideways.'
make_subtitle "$CAP_DIR/07.png" 'The air, clouds, and ocean keep their momentum too.'
make_subtitle "$CAP_DIR/08.png" $'When the ground starts again, land, air, water,\nand everything loose are no longer aligned.'
make_subtitle "$CAP_DIR/09.png" 'That mismatch is the real disaster.'
make_subtitle "$CAP_DIR/10.png" 'What moves first? You, the atmosphere, or the ocean?'

echo "[1/8] hook: no big overlay text"
encode_video "$ROOT/07_edit/story_draft_v02/flow_segments/01_shot_01_ground_lock_720p_8s.mp4" 0.00 3.60 "$WORK/01_hook.mp4"

echo "[2/8] receipt close-up: new action insert"
encode_video "$FLOW/03_receipt_motion_720p_8s.mp4" 0.30 3.64 "$WORK/03_receipt.mp4"

echo "[3/8] full-body inertia: short effective window"
encode_video "$ROOT/07_edit/story_draft_v02/flow_segments/02_shot_02_body_keeps_going_720p_8s.mp4" 1.40 6.20 "$WORK/02_inertia.mp4"

echo "[4/8] distance diagram: clean line only"
ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 24 -i "$ASSETS/shot_03_aerial_465m_plate.png" \
  -loop 1 -framerate 24 -i "$GRAPHICS/03_measure_clean_overlay.png" \
  -t 8.40 -filter_complex \
  "[0:v]scale=1080:1920:flags=lanczos,format=rgba[base];[1:v]scale=1080:1920:flags=lanczos,format=rgba[overlay];[base][overlay]overlay=0:0:format=auto[comp];[comp]scale=1188:2112:flags=lanczos,crop=1080:1920:x='54+38*min(t/8.40,1)':y='96-22*min(t/8.40,1)',format=yuv420p,setsar=1[v]" \
  -map '[v]' -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/04_distance.mp4"

echo "[5/8] gravity diagram: no title card"
ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 24 -i "$GRAPHICS/06_gravity_clean_diagram.png" -t 3.52 \
  -vf "scale=1080:1920:flags=lanczos,format=yuv420p,setsar=1" \
  -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/05_gravity.mp4"

echo "[6/8] environment layer: short, no repeated hold"
encode_video "$ROOT/07_edit/story_draft_v02/flow_segments/04_shot_04_air_cloud_ocean_720p_8s.mp4" 0.80 3.04 "$WORK/06_layers.mp4"

echo "[7/8] restart mismatch and callback"
encode_video "$ROOT/07_edit/story_draft_v02/flow_segments/05_shot_05_restart_mismatch_720p_8s.mp4" 0.00 7.92 "$WORK/07_mismatch.mp4"
encode_video "$ROOT/07_edit/story_draft_v02/flow_segments/07_shot_07_callback_720p_8s.mp4" 0.50 3.20 "$WORK/08_callback.mp4"

printf "file '%s'\n" \
  "$WORK/01_hook.mp4" \
  "$WORK/03_receipt.mp4" \
  "$WORK/02_inertia.mp4" \
  "$WORK/04_distance.mp4" \
  "$WORK/05_gravity.mp4" \
  "$WORK/06_layers.mp4" \
  "$WORK/07_mismatch.mp4" \
  "$WORK/08_callback.mp4" > "$WORK/concat.txt"

echo "[8/8] concat, right-bottom subtitles, denoised voice"
ffmpeg -hide_banner -loglevel error -y \
  -f concat -safe 0 -i "$WORK/concat.txt" \
  -c:v libx264 -preset medium -crf 17 -r 24 -pix_fmt yuv420p -an "$WORK/video_base.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$WORK/video_base.mp4" \
  -loop 1 -framerate 24 -i "$CAP_DIR/01.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/02.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/03.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/04.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/05.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/06.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/07.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/08.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/09.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/10.png" \
  -filter_complex \
  "[0:v]format=rgba[base];[base][1:v]overlay=0:0:format=auto:enable='between(t,0,3.52)'[v1];[v1][2:v]overlay=0:0:format=auto:enable='between(t,4.32,9.52)'[v2];[v2][3:v]overlay=0:0:format=auto:enable='between(t,10.24,12.80)'[v3];[v3][4:v]overlay=0:0:format=auto:enable='between(t,13.44,18.32)'[v4];[v4][5:v]overlay=0:0:format=auto:enable='between(t,18.32,21.20)'[v5];[v5][6:v]overlay=0:0:format=auto:enable='between(t,21.84,25.36)'[v6];[v6][7:v]overlay=0:0:format=auto:enable='between(t,25.36,28.40)'[v7];[v7][8:v]overlay=0:0:format=auto:enable='between(t,28.40,33.20)'[v8];[v8][9:v]overlay=0:0:format=auto:enable='between(t,33.76,35.76)'[v9];[v9][10:v]overlay=0:0:format=auto:enable='between(t,36.32,39.36)'[v]" \
  -map '[v]' -an -t 39.520167 -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p "$WORK/video_captioned.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$VOICE" \
  -af "highpass=f=70,lowpass=f=16000,afftdn=nr=8:nf=-60:tn=1,volume=5.5dB" \
  -ar 48000 -ac 1 -c:a pcm_s24le "$WORK/voice_clean.wav"

ffmpeg -hide_banner -loglevel error -y \
  -i "$WORK/video_captioned.mp4" -i "$WORK/voice_clean.wav" \
  -map 0:v:0 -map 1:a:0 -t 39.520167 \
  -c:v copy -c:a aac -b:a 256k -ar 48000 -ac 1 -shortest -movflags +faststart "$FINAL"

ffprobe -v error -show_entries format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels,duration \
  -of default=noprint_wrappers=1 "$FINAL"
echo "Wrote $FINAL"
