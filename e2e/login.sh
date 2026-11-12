#!/bin/zsh
# e2e 0.23 with sign-in scripted, so the agents are judged on the flows themselves.
set -u
cd "$(dirname "$0")"
export E2E_DEVICE="iPhone Duo"
export E2E_UDID=2A55E9B7-7D0A-486B-9152-2B5EDD8528C1
log=../results/e2e/login.log
mkdir -p ../results/e2e

install_app() {
  xcrun simctl terminate $E2E_UDID dev.yii.boxtide 2>/dev/null
  xcrun simctl install $E2E_UDID "apps/Runner-$1.app"
  echo "== installed $1 $(date +%T)" >> $log
}

run() {
  local label=$1; shift
  echo "== $label start $(date +%T)" >> $log
  ./run.sh "$label" "$@" tests/scripted-login.e2e.ts >> $log 2>&1
  echo "== $label exit $? $(date +%T)" >> $log
}

install_app normal
if [[ "${1:-}" == "smoke" ]]; then
  run "v023-login-smoke-jevv" --agent jevv --no-cache --grep 'login return-flow'
  exit 0
fi
for i in 1 2 3; do run "v023-login-normal-jev-live$i" --agent jev --no-cache; done
for i in 1 2 3; do run "v023-login-normal-jevv-live$i" --agent jevv --no-cache; done
run "v023-login-normal-lite-live1" --agent lite --no-cache

install_app chaos4
for i in 1 2; do run "v023-login-chaos-jev-live$i" --agent jev --no-cache; done
for i in 1 2; do run "v023-login-chaos-jevv-live$i" --agent jevv --no-cache; done
echo "== done $(date +%T)" >> $log
