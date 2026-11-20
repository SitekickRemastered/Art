#!/usr/bin/env bash
# Export every chip/effect library into Tools/out:
#   sprites/      one folder of frame SVGs per DefineSprite  (parts, back/front clips)
#   shapes/       one SVG per DefineShape
#   morphshapes/  one SVG per DefineMorphShape
#   lib.xml       -swf2xml timeline dump (display list per frame)
#   scripts/      AS3 sources (effect classes say which symbols a chip draws)
#   symbols.csv   SymbolClass map: symbolId -> class name
#
# FFDec only resolves the input file by absolute path for some export types, so
# every SWF is passed absolutely.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$(cd "$ROOT/.." && pwd)/Source"
OUT="$ROOT/Tools/out"
JAR="$ROOT/Tools/ffdec/ffdec.jar"
JAVA="${JAVA:-java}"

run() {  # $1 = swf, $2 = outdir, $3 = tag
	local swf="$1" dir="$2"
	mkdir -p "$dir/sprites" "$dir/shapes" "$dir/morphshapes" "$dir/scripts" "$dir/symbols"
	"$JAVA" -Xmx6g -jar "$JAR" -format sprite:svg -export sprite "$dir/sprites" "$swf" > "$dir/sprite.log" 2>&1
	"$JAVA" -Xmx6g -jar "$JAR" -format shape:svg -export shape "$dir/shapes" "$swf" > "$dir/shape.log" 2>&1
	"$JAVA" -Xmx6g -jar "$JAR" -format morphshape:svg -export morphshape "$dir/morphshapes" "$swf" > "$dir/morph.log" 2>&1
	"$JAVA" -Xmx6g -jar "$JAR" -format script:as -export script "$dir/scripts" "$swf" > "$dir/script.log" 2>&1
	"$JAVA" -Xmx6g -jar "$JAR" -format symbolClass:csv -export symbolClass "$dir/symbols" "$swf" > "$dir/symbol.log" 2>&1
	"$JAVA" -Xmx6g -jar "$JAR" -swf2xml "$swf" "$dir/lib.xml" > "$dir/xml.log" 2>&1
	echo "done $(basename "$dir"): sprites=$(ls "$dir/sprites" | wc -l) shapes=$(ls "$dir/shapes" | wc -l) morphs=$(ls "$dir/morphshapes" | wc -l)"
}

for swf in "$SRC/Effect Libraries"/*.swf; do
	tag="$(basename "$swf" .swf | sed 's/^effectlibrary//')"
	run "$swf" "$OUT/effects_$tag"
done
for swf in "$SRC/Chip Libraries"/*.swf; do
	tag="$(basename "$swf" .swf | sed 's/^chipslibrary//')"
	run "$swf" "$OUT/chips_$tag"
done
# the Sitekick itself lives in the project, not in the Source tree
run "$ROOT/SWF/sitekick.swf" "$OUT/sitekick"
echo "ALL DONE"
