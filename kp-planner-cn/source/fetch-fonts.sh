#!/usr/bin/env bash
# Downloads the OFL fonts the planner uses and makes static weights of the
# variable fonts (so PDFs embed proper TrueType fonts). Needs curl and
# fonttools (pip install fonttools). The files are ~70 MB, so they are not
# committed to git.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p fonts && cd fonts
R=https://raw.githubusercontent.com/google/fonts/main/ofl

curl -sSfo SerifVF.ttf "$R/notoserifsc/NotoSerifSC%5Bwght%5D.ttf"
curl -sSfo SansVF.ttf "$R/notosanssc/NotoSansSC%5Bwght%5D.ttf"
curl -sSfo MaShanZheng-Regular.ttf "$R/mashanzheng/MaShanZheng-Regular.ttf"

for w in 400 700 900; do fonttools varLib.instancer -q --update-name-table SerifVF.ttf wght=$w -o NotoSerifSC-$w.ttf; done
for w in 400 700; do fonttools varLib.instancer -q --update-name-table SansVF.ttf wght=$w -o NotoSansSC-$w.ttf; done
rm SerifVF.ttf SansVF.ttf
echo "Fonts ready in $(pwd)"
