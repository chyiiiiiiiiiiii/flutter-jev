#!/bin/zsh
# The whole e2e matrix, in order, on the iPhone 17e simulator.
# Normal build first, so each agent's recordings exist; then the chaos build,
# which meets those recordings the way a renamed UI meets last week's tests.
set -u
cd "$(dirname "$0")"
U=B0600F84-6242-446E-A687-3648EBC0A8BF
log=../results/e2e/matrix.log
mkdir -p ../results/e2e

install_app() {
  xcrun simctl terminate $U dev.yii.boxtide 2>/dev/null
  xcrun simctl install $U "apps/Runner-$1.app"
  echo "== installed $1 $(date +%T)" >> $log
}

run() {
  local label=$1; shift
  echo "== $label start $(date +%T)" >> $log
  ./run.sh "$label" "$@" >> $log 2>&1
  echo "== $label exit $? $(date +%T)" >> $log
}

install_app normal
for a in lite jev; do
  run "normal-$a-rec" --agent $a
  run "normal-$a-rep1" --agent $a
  run "normal-$a-rep2" --agent $a
  run "normal-$a-live2" --agent $a --no-cache
  run "normal-$a-live3" --agent $a --no-cache
done

install_app chaos4
for a in lite jev; do
  run "chaos-$a-heal" --agent $a
  run "chaos-$a-rep1" --agent $a
  run "chaos-$a-live2" --agent $a --no-cache
  run "chaos-$a-live3" --agent $a --no-cache
done
echo "== done $(date +%T)" >> $log
