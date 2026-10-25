#!/bin/zsh
# Usage: ./run.sh <label> [e2e run flags...]
# Keys come from ~/.zshrc under the names the rest of the repo uses.
set -e
cd "$(dirname "$0")"
source ~/.nvm/nvm.sh >/dev/null && nvm use 24 >/dev/null
export TYPESAFE_AI_API_KEY="$(zsh -ic 'printf %s "$TYPESAFE_API_KEY"' 2>/dev/null)"
export GOOGLE_GENERATIVE_AI_API_KEY="$(zsh -ic 'printf %s "$GEMINI_API_KEY"' 2>/dev/null)"
export DO_NOT_TRACK=1
export RUN_LABEL="$1"; shift
mkdir -p ../results/e2e
set +e
npx e2e run --reporter list,junit "$@"
code=$?
cp .e2e/report.json "../results/e2e/report-$RUN_LABEL.json"
exit $code
