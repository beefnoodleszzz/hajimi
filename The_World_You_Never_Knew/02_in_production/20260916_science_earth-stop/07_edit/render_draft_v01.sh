#!/bin/zsh
set -euo pipefail

PROJECT="/Users/zhangxiaolong/Desktop/hajimi/The_World_You_Never_Knew/02_in_production/20260916_science_earth-stop"
VISUALS="$PROJECT/05_visuals/generated_v01"
OUT="$PROJECT/07_edit/draft_v01"
VO_SOURCE="/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/20260916_science_earth_stop_tts_v01/run_0001/VO_TTS_MAIN/candidate_01.wav"
FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"

mkdir -p "$OUT/segments"
mkdir -p "$OUT/graphics"
cp "$VO_SOURCE" "$OUT/voiceover_candidate_01.wav"

make_still() {
  local image="$1"
  local duration="$2"
  local output="$3"
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "$image" -t "$duration" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,format=yuv420p" \
    -r 30 -an -c:v libx264 -preset medium -crf 18 "$output"
}

make_graphic_a() {
  local graphic="$OUT/graphics/03_equator_465ms.png"
  magick -size 1080x1920 xc:'#07111f' \
    -stroke '#15304c' -strokewidth 6 -fill none -draw 'rectangle 100,530 980,1330' \
    -stroke none -fill '#48d8ff' -draw 'rectangle 180,1120 900,1126' \
    -gravity North -fill '#94aeca' -font "$FONT" -pointsize 42 -annotate +0+700 'AT THE EQUATOR' \
    -fill '#effaff' -pointsize 132 -annotate +0+820 '465 m/s' \
    -fill '#48d8ff' -pointsize 34 -annotate +0+1010 'EASTWARD VELOCITY' \
    -depth 8 "$graphic"
  make_still "$graphic" 4.5 "$1"
}

make_graphic_b() {
  local graphic="$OUT/graphics/05_465m_one_second.png"
  magick -size 1080x1920 xc:'#07111f' \
    -stroke none -fill '#48d8ff' -draw 'rectangle 120,760 960,770' \
    -fill '#94aeca' -draw 'rectangle 220,700 226,830' -draw 'rectangle 860,700 866,830' \
    -gravity North -font "$FONT" -fill '#94aeca' -pointsize 40 -annotate +0+520 'SIMPLIFIED MODEL' \
    -fill '#effaff' -pointsize 132 -annotate +0+900 '~465 m' \
    -fill '#48d8ff' -pointsize 48 -annotate +0+1110 'IN ONE SECOND' \
    -depth 8 "$graphic"
  make_still "$graphic" 4.5 "$1"
}

make_graphic_c() {
  local graphic="$OUT/graphics/09_coriolis.png"
  magick -size 1080x1920 xc:'#07111f' \
    -stroke none -fill '#48d8ff' -draw 'rectangle 150,630 930,636' -draw 'rectangle 150,1140 930,1146' \
    -fill '#29445d' -draw 'rectangle 450,635 456,1140' \
    -gravity North -font "$FONT" -fill '#effaff' -pointsize 68 -annotate +0+420 'CORIOLIS EFFECT' \
    -fill '#94aeca' -pointsize 42 -annotate +0+710 'NORTH' \
    -annotate +0+1220 'SOUTH' \
    -fill '#48d8ff' -pointsize 34 -annotate +0+920 'WIND + OCEAN CURRENTS' \
    -depth 8 "$graphic"
  make_still "$graphic" 6.5 "$1"
}

make_still "$VISUALS/shot_01_hook_earth_stop.png" 2.5 "$OUT/segments/01.mp4"
make_still "$VISUALS/shot_02_ground_stops_loose_motion.png" 4.0 "$OUT/segments/02.mp4"
make_graphic_a "$OUT/segments/03.mp4"
make_still "$VISUALS/shot_04_coastal_layers.png" 5.0 "$OUT/segments/04.mp4"
make_graphic_b "$OUT/segments/05.mp4"
make_still "$VISUALS/shot_06_polar_contrast.png" 4.0 "$OUT/segments/06.mp4"
make_still "$VISUALS/shot_07_gravity_contact.png" 4.5 "$OUT/segments/07.mp4"
make_still "$VISUALS/shot_08_restart_mismatch_model.png" 6.0 "$OUT/segments/08.mp4"
make_graphic_c "$OUT/segments/09.mp4"
make_still "$VISUALS/shot_10_final_orbit.png" 4.740167 "$OUT/segments/10.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$OUT/segments/01.mp4" -i "$OUT/segments/02.mp4" -i "$OUT/segments/03.mp4" \
  -i "$OUT/segments/04.mp4" -i "$OUT/segments/05.mp4" -i "$OUT/segments/06.mp4" \
  -i "$OUT/segments/07.mp4" -i "$OUT/segments/08.mp4" -i "$OUT/segments/09.mp4" \
  -i "$OUT/segments/10.mp4" \
  -filter_complex "[0:v][1:v][2:v][3:v][4:v][5:v][6:v][7:v][8:v][9:v]concat=n=10:v=1:a=0,format=yuv420p[v]" \
  -map "[v]" -r 30 -c:v libx264 -preset medium -crf 18 "$OUT/picture_lock_v01.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$OUT/picture_lock_v01.mp4" -i "$OUT/voiceover_candidate_01.wav" \
  -map 0:v:0 -map 1:a:0 -t 46.240167 \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart \
  "$OUT/short_review_v01.mp4"

ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name,codec_type,sample_rate,channels \
  -of json "$OUT/short_review_v01.mp4" > "$OUT/short_review_v01.probe.json"

echo "$OUT/short_review_v01.mp4"
