#!/bin/zsh
# e2e 0.23 on a fresh en-US simulator. A simulator set to a Chinese keyboard corrupts typed text.
set -u
cd "$(dirname "$0")"
export E2E_DEVICE="iPhone Duo E2E"
export E2E_UDID=EB139E18-594A-4082-BAA6-1635671505DF
log=../results/e2e/merge.log
traces=/private/tmp/claude-501/-Users-yii-Documents-Obsidian-Vault/b5b9ebcc-b6d1-4d60-b560-204c83e0daeb/scratchpad/traces
mkdir -p ../results/e2e $traces

install_app() {
  xcrun simctl terminate $E2E_UDID dev.yii.boxtide 2>/dev/null
  xcrun simctl install $E2E_UDID "apps/Runner-$1.app"
  echo "== installed $1 $(date +%T)" >> $log
}

run() {
  local label=$1 file=$2; shift 2
  echo "== $label start $(date +%T)" >> $log
  ./run.sh "$label" "$@" "$file" >> $log 2>&1
  echo "== $label exit $? $(date +%T)" >> $log
  cp -R .e2e/results "$traces/$label"
}

agent=tests/boxtide.e2e.ts
login=tests/scripted-login.e2e.ts
install_app merge
run v023m-login-jev-live1 $login --agent jev --no-cache
run v023m-login-jevv-live1 $login --agent jevv --no-cache
run v023m-normal-jev-live1 $agent --agent jev --no-cache
echo "== done $(date +%T)" >> $log
