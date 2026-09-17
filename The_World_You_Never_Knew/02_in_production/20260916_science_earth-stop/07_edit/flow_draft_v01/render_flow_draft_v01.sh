#!/bin/zsh
set -euo pipefail

PROJECT="/Users/zhangxiaolong/Desktop/hajimi/The_World_You_Never_Knew/02_in_production/20260916_science_earth-stop"
FLOW_RAW="$PROJECT/07_edit/flow_draft_v01/flow_segments"
OUT="$PROJECT/07_edit/flow_draft_v01"
SEGMENTS="$OUT/segments"
GRAPHICS="$PROJECT/07_edit/draft_v01/graphics"
CAP_SOURCE="$PROJECT/07_edit/draft_v02/captions"
CAP="$OUT/captions"
VOICE="/Users/zhangxiaolong/AI/voxcpm2-local/outputs/raw/friend_asmr_full_redo_20260917_v01/run_0001/FULL_CANDIDATES/full_candidate_02.wav"

mkdir -p "$SEGMENTS" "$CAP"

VOICE_DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$VOICE")
BASE_DUR=46.240167
SCALE=$(awk -v total="$VOICE_DUR" -v base="$BASE_DUR" 'BEGIN { printf "%.9f", total / base }')

D1=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 2.5*s }')
D2=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 4*s }')
D3=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 4.5*s }')
D4=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 5*s }')
D5=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 4.5*s }')
D6=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 4*s }')
D7=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 4.5*s }')
D8=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 6*s }')
D9=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 6.5*s }')
D10=$(awk -v s="$SCALE" 'BEGIN { printf "%.6f", 4.740167*s }')

T1="$D1"
T2=$(awk -v a="$D1" -v b="$D2" 'BEGIN { printf "%.6f", a+b }')
T6=$(awk -v a="$D1" -v b="$D2" -v c="$D3" -v d="$D4" -v e="$D5" -v f="$D6" 'BEGIN { printf "%.6f", a+b+c+d+e+f }')
T7=$(awk -v a="$T6" -v b="$D7" 'BEGIN { printf "%.6f", a+b }')
T9=$(awk -v a="$T7" -v b="$D8" -v c="$D9" 'BEGIN { printf "%.6f", a+b+c }')

make_flow_segment() {
  local input="$1"
  local output="$2"
  local duration="$3"
  ffmpeg -hide_banner -loglevel error -y \
    -i "$input" -t "$duration" -an \
    -vf "scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p" \
    -r 30 -c:v libx264 -preset medium -crf 18 "$output"
}

make_graphic_segment() {
  local input="$1"
  local output="$2"
  local duration="$3"
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "$input" -t "$duration" \
    -vf "scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p" \
    -r 30 -an -c:v libx264 -preset medium -crf 18 "$output"
}

make_flow_segment "$FLOW_RAW/01_shot_01_hook_720p_8s.mp4" "$SEGMENTS/01.mp4" "$D1"
make_flow_segment "$FLOW_RAW/02_shot_02_city_motion_720p_8s.mp4" "$SEGMENTS/02.mp4" "$D2"
make_graphic_segment "$GRAPHICS/03_equator_465ms.png" "$SEGMENTS/03.mp4" "$D3"
make_flow_segment "$FLOW_RAW/04_shot_04_coastal_layers_720p_8s.mp4" "$SEGMENTS/04.mp4" "$D4"
make_graphic_segment "$GRAPHICS/05_465m_one_second.png" "$SEGMENTS/05.mp4" "$D5"
make_flow_segment "$FLOW_RAW/06_shot_06_polar_contrast_720p_8s.mp4" "$SEGMENTS/06.mp4" "$D6"
make_flow_segment "$FLOW_RAW/07_shot_07_gravity_contact_720p_8s.mp4" "$SEGMENTS/07.mp4" "$D7"
make_flow_segment "$FLOW_RAW/08_shot_08_restart_mismatch_720p_8s.mp4" "$SEGMENTS/08.mp4" "$D8"
make_graphic_segment "$GRAPHICS/09_coriolis.png" "$SEGMENTS/09.mp4" "$D9"
make_flow_segment "$FLOW_RAW/10_shot_10_final_orbit_720p_8s.mp4" "$SEGMENTS/10.mp4" "$D10"

typeset -a input_args
for segment in "$SEGMENTS"/01.mp4 "$SEGMENTS"/02.mp4 "$SEGMENTS"/03.mp4 "$SEGMENTS"/04.mp4 "$SEGMENTS"/05.mp4 "$SEGMENTS"/06.mp4 "$SEGMENTS"/07.mp4 "$SEGMENTS"/08.mp4 "$SEGMENTS"/09.mp4 "$SEGMENTS"/10.mp4; do
  input_args+=( -i "$segment" )
done

concat_labels=""
for index in {0..9}; do
  concat_labels+="[${index}:v]"
done

ffmpeg -hide_banner -loglevel error -y \
  "${input_args[@]}" \
  -filter_complex "${concat_labels}concat=n=10:v=1:a=0,format=yuv420p[v]" \
  -map "[v]" -r 30 -c:v libx264 -preset medium -crf 18 \
  "$OUT/picture_lock_flow_v01.mp4"

cp "$CAP_SOURCE/earth_stops.png" "$CAP/earth_stops.png"
cp "$CAP_SOURCE/you_keep_moving.png" "$CAP/you_keep_moving.png"
cp "$CAP_SOURCE/gravity_still_works.png" "$CAP/gravity_still_works.png"
cp "$CAP_SOURCE/what_moves_first.png" "$CAP/what_moves_first.png"

ffmpeg -hide_banner -loglevel error -y \
  -i "$OUT/picture_lock_flow_v01.mp4" \
  -i "$CAP/earth_stops.png" -i "$CAP/you_keep_moving.png" \
  -i "$CAP/gravity_still_works.png" -i "$CAP/what_moves_first.png" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto:enable='between(t,0,$T1)'[v1];[v1][2:v]overlay=0:0:format=auto:enable='between(t,$T1,$T2)'[v2];[v2][3:v]overlay=0:0:format=auto:enable='between(t,$T6,$T7)'[v3];[v3][4:v]overlay=0:0:format=auto:enable='between(t,$T9,$VOICE_DUR)'[v]" \
  -map "[v]" -r 30 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  "$OUT/picture_captioned_flow_v01.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "$OUT/picture_captioned_flow_v01.mp4" -i "$VOICE" \
  -map 0:v:0 -map 1:a:0 -t "$VOICE_DUR" \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 1 -shortest -movflags +faststart \
  "$OUT/earth_stop_flow_review_v01.mp4"

ffprobe -v error \
  -show_entries format=duration,size:stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels,duration \
  -of json "$OUT/earth_stop_flow_review_v01.mp4" > "$OUT/earth_stop_flow_review_v01.probe.json"

printf '%s\n' "$OUT/earth_stop_flow_review_v01.mp4"
