#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EDIT="$ROOT/07_edit/story_draft_v02"
FLOW="$EDIT/flow_segments"
ASSETS="$ROOT/05_visuals/generated_v03_story"
GRAPHICS="$EDIT/graphics"
VOICE="$ROOT/04_voice/story_v02/voiceover_story_v02.wav"
CAPTIONS="$EDIT/captions_story_v02.ass"
WORK="$EDIT/render_work"
FINAL="$EDIT/earth_stop_story_v02_review.mp4"
FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
CAP_DIR="$WORK/captions"

mkdir -p "$WORK"
mkdir -p "$CAP_DIR"

make_caption() {
  local output="$1"
  local gravity="$2"
  local pointsize="$3"
  local offset="$4"
  local fill="$5"
  local text="$6"
  magick -size 1080x1920 xc:none -gravity "$gravity" \
    -font "$FONT" -pointsize "$pointsize" -stroke '#07111f' -strokewidth 4 -fill "$fill" \
    -annotate "$offset" "$text" -depth 8 "$output"
}

make_caption "$CAP_DIR/hook_title.png" North 92 +0+1280 '#effaff' 'THE GROUND STOPS'
make_caption "$CAP_DIR/hook_speed.png" North 36 +0+1435 '#b9f2ff' '465 METERS PER SECOND  /  AT THE EQUATOR'
make_caption "$CAP_DIR/inertia.png" North 72 +0+1320 '#effaff' 'YOU KEEP MOVING EAST'
make_caption "$CAP_DIR/inertia_sub.png" North 44 +0+1430 '#b9f2ff' 'INERTIA IS SIDEWAYS'
make_caption "$CAP_DIR/layers.png" North 40 +0+220 '#b9f2ff' 'AIR  /  CLOUDS  /  OCEAN'
make_caption "$CAP_DIR/mismatch.png" North 52 +0+210 '#effaff' 'LAND RESTARTS FIRST'
make_caption "$CAP_DIR/disaster.png" North 58 +0+1450 '#ffb9b0' 'MISMATCH = DISASTER'
make_caption "$CAP_DIR/question.png" North 82 +0+1300 '#effaff' 'WHAT MOVES FIRST?'

echo "[1/8] street hook"
ffmpeg -hide_banner -loglevel error -y \
  -i "$FLOW/01_shot_01_ground_lock_720p_8s.mp4" \
  -loop 1 -framerate 24 -i "$CAP_DIR/hook_title.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/hook_speed.png" \
  -t 7.50 -filter_complex \
  "[0:v]scale=1080:1920:flags=lanczos,setsar=1[base];[base][1:v]overlay=0:0:format=auto:enable='between(t,0,3.7)'[v1];[v1][2:v]overlay=0:0:format=auto:enable='between(t,3.7,7.5)'[v]" \
  -map '[v]' -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/01_hook.mp4"

echo "[2/8] inertia continuation"
ffmpeg -hide_banner -loglevel error -y \
  -i "$FLOW/02_shot_02_body_keeps_going_720p_8s.mp4" \
  -loop 1 -framerate 24 -i "$CAP_DIR/inertia.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/inertia_sub.png" \
  -t 5.92 -filter_complex \
  "[0:v]scale=1080:1920:flags=lanczos,setsar=1[base];[base][1:v]overlay=0:0:format=auto[v1];[v1][2:v]overlay=0:0:format=auto[v]" \
  -map '[v]' -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/02_inertia.mp4"

echo "[3/8] 465 meter explanation"
ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -i "$ASSETS/shot_03_aerial_465m_plate.png" \
  -loop 1 -i "$GRAPHICS/03_measure_465m_overlay.png" \
  -t 8.38 \
  -filter_complex "[0:v]scale=1080:1920:flags=lanczos,format=rgba[base];[1:v]scale=1080:1920:flags=lanczos,format=rgba[overlay];[base][overlay]overlay=0:0:shortest=1,format=yuv420p,setsar=1" \
  -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/03_measure.mp4"

echo "[4/8] gravity graphic"
ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -i "$GRAPHICS/06_gravity_sideways_overlay.png" -t 3.56 \
  -vf "scale=1080:1920:flags=lanczos,format=yuv420p,setsar=1" \
  -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/04_gravity.mp4"

echo "[5/8] air, clouds, ocean"
ffmpeg -hide_banner -loglevel error -y \
  -i "$FLOW/04_shot_04_air_cloud_ocean_720p_8s.mp4" \
  -loop 1 -framerate 24 -i "$CAP_DIR/layers.png" \
  -t 2.62 -filter_complex \
  "[0:v]scale=1080:1920:flags=lanczos,setsar=1[base];[base][1:v]overlay=0:0:format=auto[v]" \
  -map '[v]' -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/05_layers.mp4"

echo "[6/8] restart mismatch"
ffmpeg -hide_banner -loglevel error -y \
  -i "$FLOW/05_shot_05_restart_mismatch_720p_8s.mp4" \
  -loop 1 -framerate 24 -i "$CAP_DIR/mismatch.png" \
  -loop 1 -framerate 24 -i "$CAP_DIR/disaster.png" \
  -t 8.00 -filter_complex \
  "[0:v]scale=1080:1920:flags=lanczos,setsar=1[base];[base][1:v]overlay=0:0:format=auto:enable='between(t,0.4,3.8)'[v1];[v1][2:v]overlay=0:0:format=auto:enable='between(t,4.2,8.0)'[v]" \
  -map '[v]' -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/06_mismatch.mp4"

echo "[7/8] callback ending"
ffmpeg -hide_banner -loglevel error -y \
  -i "$FLOW/07_shot_07_callback_720p_8s.mp4" \
  -loop 1 -framerate 24 -i "$CAP_DIR/question.png" \
  -t 3.54 -filter_complex \
  "[0:v]scale=1080:1920:flags=lanczos,setsar=1[base];[base][1:v]overlay=0:0:format=auto[v]" \
  -map '[v]' -an -r 24 -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p \
  "$WORK/07_callback.mp4"

cat > "$WORK/concat.txt" <<EOF
file '$WORK/01_hook.mp4'
file '$WORK/02_inertia.mp4'
file '$WORK/03_measure.mp4'
file '$WORK/04_gravity.mp4'
file '$WORK/05_layers.mp4'
file '$WORK/06_mismatch.mp4'
file '$WORK/07_callback.mp4'
EOF

echo "[8/8] concat, captions, voice"
ffmpeg -hide_banner -loglevel error -y \
  -f concat -safe 0 -i "$WORK/concat.txt" \
  -c:v libx264 -preset medium -crf 17 -r 24 -pix_fmt yuv420p -an \
  "$WORK/video_base.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$WORK/video_base.mp4" -i "$VOICE" \
  -map 0:v:0 -map 1:a:0 -c:v libx264 -preset medium -crf 17 -r 24 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -af "loudnorm=I=-16:TP=-1.5:LRA=11" -shortest \
  "$FINAL"

ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,sample_rate,channels \
  -of default=noprint_wrappers=1 "$FINAL"
echo "Wrote $FINAL"
