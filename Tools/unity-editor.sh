#!/usr/bin/env bash
# Run the Unity Editor from a shell without losing the licence.
#
# Unity Hub here is the Flatpak (com.unity.UnityHub), so it activates the seat
# and refreshes the licence *inside its sandbox*:
#
#   ~/.var/app/com.unity.UnityHub/data/unity3d/Unity/Unity_lic.ulf
#   ~/.var/app/com.unity.UnityHub/config/unity3d/Unity/licenses/UnityEntitlementLicense.xml
#
# An editor started from a shell has HOME=~, reads
#
#   ~/.local/share/unity3d/Unity/Unity_lic.ulf
#   ~/.config/unity3d/Unity/licenses/UnityEntitlementLicense.xml
#
# and exits 198 with "No valid Unity Editor license found" when those are
# missing or stale.  This copies them across when needed, then execs the editor
# with every argument passed through, so batchmode works after a Hub refresh:
#
#   Tools/unity-editor.sh -batchmode -nographics -quit -projectPath Unity
#   Tools/unity-editor.sh -batchmode -nographics -quit -projectPath Unity \
#       -executeMethod Sitekick.ChipMovieBuilder.RunFromCommandLine --chip 14
#
# UNITY_EDITOR overrides the editor binary (default: newest installed under
# ~/Unity/Hub/Editor).  UNITY_HUB_SANDBOX overrides the sandbox root.

set -euo pipefail

hub=${UNITY_HUB_SANDBOX:-$HOME/.var/app/com.unity.UnityHub}

ulf_src=$hub/data/unity3d/Unity/Unity_lic.ulf
ent_src=$hub/config/unity3d/Unity/licenses/UnityEntitlementLicense.xml
ulf_dst=$HOME/.local/share/unity3d/Unity/Unity_lic.ulf
ent_dst=$HOME/.config/unity3d/Unity/licenses/UnityEntitlementLicense.xml

refresh() {
	local src=$1 dst=$2
	[[ -f $src ]] || return 0
	if [[ ! -f $dst || $src -nt $dst ]]; then
		mkdir -p "$(dirname "$dst")"
		cp -p "$src" "$dst"
		echo "unity-editor: refreshed $dst" >&2
	fi
}

refresh "$ulf_src" "$ulf_dst"
refresh "$ent_src" "$ent_dst"

if [[ ! -f $ulf_dst && ! -f $ent_dst ]]; then
	echo "unity-editor: warning: no licence at $ulf_dst - open Unity Hub and sign in" >&2
fi

editor=${UNITY_EDITOR:-}
if [[ -z $editor ]]; then
	editor=$(find "$HOME/Unity/Hub/Editor" -mindepth 3 -maxdepth 3 \
		-type f -name Unity -perm -u+x 2>/dev/null | sort -V | tail -n 1)
fi
if [[ -z $editor || ! -x $editor ]]; then
	echo "unity-editor: no Unity editor found; set UNITY_EDITOR=/path/to/Editor/Unity" >&2
	exit 1
fi

exec "$editor" "$@"
