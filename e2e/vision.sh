#!/bin/zsh
# e2e 0.23 on a current simulator: does Jev get through once it can see the screen?
# The no-vision Jev and LLM runs are the controls, so a change can be told apart
# from the newer e2e or the newer iOS.
set -u
cd "$(dirname "$0")"
export E2E_DEVICE="iPhone Duo"
export E2E_UDID=2A55E9B7-7D0A-486B-9152-2B5EDD8528C1
log=../results/e2e/vision.log
mkdir -p ../results/e2e

install_app() {
  xcrun simctl terminate $E2E_UDID dev.yii.boxtide 2>/dev/null
  xcrun simctl install $E2E_UDID "apps/Runner-$1.app"
  echo "== installed $1 $(date +%T)" >> $log
}

run() {
  local label=$1; shift
  echo "== $label start $(date +%T)" >> $log
  ./run.sh "$label" "$@" tests/boxtide.e2e.ts >> $log 2>&1
  echo "== $label exit $? $(date +%T)" >> $log
}

if [[ "${1:-}" == "smoke" ]]; then
  install_app normal
  run "v023-smoke-jevv" --agent jevv --no-cache --grep return-flow
  exit 0
fi

install_app normal
run "v023-normal-jev-live1" --agent jev --no-cache
run "v023-normal-lite-live1" --agent lite --no-cache
run "v023-normal-jevv-live1" --agent jevv --no-cache
run "v023-normal-jevv-live2" --agent jevv --no-cache
run "v023-normal-jevv-live3" --agent jevv --no-cache

install_app chaos4
run "v023-chaos-jevv-live1" --agent jevv --no-cache
run "v023-chaos-jevv-live2" --agent jevv --no-cache
echo "== done $(date +%T)" >> $log
