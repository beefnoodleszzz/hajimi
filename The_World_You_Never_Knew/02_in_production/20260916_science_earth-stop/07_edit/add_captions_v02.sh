#!/bin/zsh
set -euo pipefail

PROJECT="/Users/zhangxiaolong/Desktop/hajimi/The_World_You_Never_Knew/02_in_production/20260916_science_earth-stop"
IN="$PROJECT/07_edit/draft_v01"
OUT="$PROJECT/07_edit/draft_v02"
CAP="$OUT/captions"
FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"

mkdir -p "$CAP"
cp "$IN/voiceover_candidate_01.wav" "$OUT/voiceover_candidate_01.wav"

magick -size 1080x1920 xc:none -gravity North \
  -font "$FONT" -pointsize 92 -stroke '#07111f' -strokewidth 4 -fill '#effaff' \
  -annotate +0+220 'EARTH STOPS' -depth 8 "$CAP/earth_stops.png"

magick -size 1080x1920 xc:none -gravity Center \
  -font "$FONT" -pointsize 86 -stroke '#07111f' -strokewidth 4 -fill '#effaff' \
  -annotate +0-80 'YOU KEEP MOVING' -depth 8 "$CAP/you_keep_moving.png"

magick -size 1080x1920 xc:none -gravity North \
  -font "$FONT" -pointsize 72 -stroke '#07111f' -strokewidth 4 -fill '#effaff' \
  -annotate +0+300 'GRAVITY STILL WORKS' -depth 8 "$CAP/gravity_still_works.png"

magick -size 1080x1920 xc:none -gravity Center \
  -font "$FONT" -pointsize 82 -stroke '#07111f' -strokewidth 4 -fill '#effaff' \
  -annotate +0+0 'WHAT MOVES FIRST?' -depth 8 "$CAP/what_moves_first.png"

ffmpeg -hide_banner -loglevel error -y \
  -i "$IN/picture_lock_v01.mp4" \
  -i "$CAP/earth_stops.png" -i "$CAP/you_keep_moving.png" \
  -i "$CAP/gravity_still_works.png" -i "$CAP/what_moves_first.png" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto:enable='between(t,0,2.5)'[v1];[v1][2:v]overlay=0:0:format=auto:enable='between(t,2.5,6.5)'[v2];[v2][3:v]overlay=0:0:format=auto:enable='between(t,24.5,29.0)'[v3];[v3][4:v]overlay=0:0:format=auto:enable='between(t,41.5,46.24)'[v]" \
  -map "[v]" -r 30 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  "$OUT/picture_captioned_v02.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$OUT/picture_captioned_v02.mp4" -i "$OUT/voiceover_candidate_01.wav" \
  -map 0:v:0 -map 1:a:0 -t 46.240167 \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart \
  "$OUT/short_review_v02.mp4"

ffprobe -v error -show_entries format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration \
  -of json "$OUT/short_review_v02.mp4" > "$OUT/short_review_v02.probe.json"

echo "$OUT/short_review_v02.mp4"
