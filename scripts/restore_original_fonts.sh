#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN="ade3d1533e06b2b1462ffcde8e08b129627ca360"
BASE="https://raw.githubusercontent.com/google/fonts/${PIN}"
DEST1="$ROOT/web/assets/fonts"
DEST2="$ROOT/prismora_lab/assets/web/assets/fonts"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/prismora-fonts.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST1" "$DEST2"

hash_blob() {
  python3 - "$1" <<'PY'
import hashlib, pathlib, sys
p=pathlib.Path(sys.argv[1]); b=p.read_bytes()
print(hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest())
PY
}
fetch_asset() {
  rel="$1"; name="$2"; expected="$3"
  url="$BASE/$rel"
  out="$TMP/$name"
  echo "→ $name"
  curl -fL --retry 3 --connect-timeout 15 "$url" -o "$out"
  actual="$(hash_blob "$out")"
  if [ "$actual" != "$expected" ]; then
    echo "ERREUR hash Git blob pour $name" >&2
    echo "attendu: $expected" >&2
    echo "obtenu : $actual" >&2
    exit 21
  fi
  cp "$out" "$DEST1/$name"
  cp "$out" "$DEST2/$name"
}

fetch_asset "ofl/spectral/Spectral-Light.ttf" "Spectral-Light.ttf" "852e7d67ad79d72bd5b0ded7242991483c999df0"
fetch_asset "ofl/spectral/Spectral-Regular.ttf" "Spectral-Regular.ttf" "25a6c47f8050e4ea3c9713a02a4843a8d6c503d5"
fetch_asset "ofl/spectral/Spectral-Medium.ttf" "Spectral-Medium.ttf" "77420e8ea8155bd3a36960a94d6edd1fcc0e3661"
fetch_asset "ofl/spectral/Spectral-LightItalic.ttf" "Spectral-LightItalic.ttf" "0d3c3b6f92dd04b983a6c2703c36147f960443dd"
fetch_asset "ofl/spectral/Spectral-Italic.ttf" "Spectral-Italic.ttf" "99d6c2def129dea2daa47652c2168c271c7a59a7"
fetch_asset "ofl/albertsans/AlbertSans%5Bwght%5D.ttf" "AlbertSans-wght.ttf" "aa28110751a034a03ba84a7de12d069c3f652fe7"
fetch_asset "ofl/albertsans/AlbertSans-Italic%5Bwght%5D.ttf" "AlbertSans-Italic-wght.ttf" "e632b1c74e89d59bd1942d95a813e03530dfae7e"
fetch_asset "ofl/splinesansmono/SplineSansMono%5Bwght%5D.ttf" "SplineSansMono-wght.ttf" "41f36d3500e0f4b559fc56b31d5fb4718b78690c"
fetch_asset "ofl/splinesansmono/SplineSansMono-Italic%5Bwght%5D.ttf" "SplineSansMono-Italic-wght.ttf" "8ea9851d4e563d5f5ca7e51b68f6e04b60021f4f"
fetch_asset "ofl/spectral/OFL.txt" "OFL-Spectral.txt" "163d3a50c1666a69aac8b9f78dfc7142fb319a27"
fetch_asset "ofl/albertsans/OFL.txt" "OFL-Albert-Sans.txt" "958d457848e6ed0643d0092fe7d7740adb88971a"
fetch_asset "ofl/splinesansmono/OFL.txt" "OFL-Spline-Sans-Mono.txt" "ebcad12ff04eb1323a4ae37494ee62289579b36a"

python3 - "$DEST1" "$DEST2" <<'PY'
from pathlib import Path
import sys
one,two=map(Path,sys.argv[1:3])
fonts=[
'Spectral-Light.ttf','Spectral-Regular.ttf','Spectral-Medium.ttf','Spectral-LightItalic.ttf','Spectral-Italic.ttf',
'AlbertSans-wght.ttf','AlbertSans-Italic-wght.ttf','SplineSansMono-wght.ttf','SplineSansMono-Italic-wght.ttf']
for name in fonts:
    a,b=one/name,two/name
    assert a.stat().st_size>0, name
    assert a.read_bytes()==b.read_bytes(), name
print(f"Polices vérifiées: {len(fonts)}/9, miroirs byte-identiques.")
PY

echo "OK — typographie originale restaurée localement depuis google/fonts@$PIN"
