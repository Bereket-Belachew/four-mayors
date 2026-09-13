#!/bin/sh
# bump cache-busting version tags on the 3D page's scripts
cd "$(dirname "$0")" && python3 - <<'EOF2'
import re, time
v=str(int(time.time()))
for p,pat in [("city3d.js", r'(from "\./(?:cinema|callouts|hero)\.js)\?v=\d+"'), ("city3d.html", r'(src="(?:city3d|narrator|tech|runpanel)\.js)\?v=\d+"')]:
    s=open(p).read(); s=re.sub(pat, lambda m: m.group(1)+"?v="+v+'"', s); open(p,"w").write(s)
print("bumped", v)
EOF2
