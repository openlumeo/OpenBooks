#!/bin/sh
# Cut over the inference engine with a recorded rollback target.
#   deploy/rollout.sh deploy <tag>   build, smoke-test a candidate beside the live engine, promote only on pass
#   deploy/rollout.sh rollback       restore the previous tag recorded in deploy/.rollout-state
#   deploy/rollout.sh status
# Env: OPENBOOKS_COMPOSE_FILE (default deploy/compose.inference.yaml), OPENBOOKS_ENGINE_SERVICES (default "engine";
# use "engine-a engine-b" with compose.replicas.yaml: replicas are replaced one at a time so one is always ready),
# OPENBOOKS_LIVE_URL (default http://127.0.0.1:8765), OPENBOOKS_CANDIDATE_PORT (default 8766), OPENBOOKS_SKIP_BUILD=1.
set -eu
cd "$(dirname "$0")/.."
STATE=deploy/.rollout-state
COMPOSE_FILE=${OPENBOOKS_COMPOSE_FILE:-deploy/compose.inference.yaml}
SERVICES=${OPENBOOKS_ENGINE_SERVICES:-engine}
LIVE=${OPENBOOKS_LIVE_URL:-http://127.0.0.1:8765}
CPORT=${OPENBOOKS_CANDIDATE_PORT:-8766}
CAND=openbooks-engine-candidate

die() { echo "rollout: $*" >&2; exit 1; }
usage() { echo "Usage: deploy/rollout.sh deploy <tag> | rollback | status" >&2; exit 2; }
get() { [ -f "$STATE" ] && sed -n "s/^$1=//p" "$STATE" | tail -n 1 || true; }
digest() { docker image inspect --format '{{.Id}}' "openbooks-engine:$1"; }
model() { node -e 'fetch(process.argv[1]+"/v1/health").then(r=>r.json()).then(h=>console.log(JSON.stringify(h.model_identity)))' "$1"; }
wait_ready() { # url
  i=0
  until node -e 'fetch(process.argv[1]+"/readyz").then(r=>process.exit(r.ok?0:1),()=>process.exit(1))' "$1"; do
    i=$((i+1)); [ "$i" -le 60 ] || return 1; sleep 2
  done
}
smoke() { node deploy/smoke.mjs --engine "$1"; }
cleanup() { docker rm -f "$CAND" >/dev/null 2>&1 || true; }
write_state() { # cur_tag cur_digest cur_model prev_tag prev_digest prev_model
  printf 'CURRENT_TAG=%s\nCURRENT_DIGEST=%s\nCURRENT_MODEL=%s\nPREVIOUS_TAG=%s\nPREVIOUS_DIGEST=%s\nPREVIOUS_MODEL=%s\n' \
    "$1" "$2" "$3" "$4" "$5" "$6" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
}
switch_live() { # tag: replace each engine in turn; compose drains the old one (SIGTERM, 130s grace)
  for svc in $SERVICES; do
    OPENBOOKS_ENGINE_TAG="$1" docker compose -f "$COMPOSE_FILE" up -d --no-deps --wait "$svc"
  done
}

cmd=${1:-}
case "$cmd" in
deploy)
  tag=${2:-}
  [ -n "$tag" ] || usage
  trap cleanup EXIT
  [ "${OPENBOOKS_SKIP_BUILD:-}" = 1 ] || docker build -f deploy/engine.Dockerfile -t "openbooks-engine:$tag" .
  new_digest=$(digest "$tag")
  # Candidate runs beside the live engine, which keeps serving until the candidate has passed.
  cleanup
  docker run -d --name "$CAND" -p "127.0.0.1:$CPORT:8765" "openbooks-engine:$tag" >/dev/null
  wait_ready "http://127.0.0.1:$CPORT" || die "candidate never became ready; live engine untouched"
  smoke "http://127.0.0.1:$CPORT" || die "candidate failed the smoke test; live engine untouched"
  new_model=$(model "http://127.0.0.1:$CPORT")
  cleanup
  cur_tag=$(get CURRENT_TAG)
  if [ -n "$cur_tag" ]; then
    write_state "$tag" "$new_digest" "$new_model" "$cur_tag" "$(get CURRENT_DIGEST)" "$(get CURRENT_MODEL)"
  else
    write_state "$tag" "$new_digest" "$new_model" "" "" ""
  fi
  switch_live "$tag"
  if wait_ready "$LIVE" && smoke "$LIVE"; then
    echo "rollout: promoted $tag ($new_digest) model=$new_model"
  else
    echo "rollout: live check failed, rolling back" >&2
    [ -n "$cur_tag" ] || die "no previous tag recorded to roll back to"
    exec "$0" rollback
  fi
  ;;
rollback)
  prev=$(get PREVIOUS_TAG)
  [ -n "$prev" ] || die "no previous tag in $STATE"
  docker image inspect "openbooks-engine:$prev" >/dev/null 2>&1 || die "previous image openbooks-engine:$prev is not on this host"
  cur_tag=$(get CURRENT_TAG); cur_digest=$(get CURRENT_DIGEST); cur_model=$(get CURRENT_MODEL)
  prev_digest=$(get PREVIOUS_DIGEST); prev_model=$(get PREVIOUS_MODEL)
  switch_live "$prev"
  wait_ready "$LIVE" || die "previous tag $prev did not become ready"
  smoke "$LIVE" || die "previous tag $prev failed the smoke test"
  write_state "$prev" "$prev_digest" "$prev_model" "$cur_tag" "$cur_digest" "$cur_model"
  echo "rollout: restored $prev"
  ;;
status)
  [ -f "$STATE" ] && cat "$STATE" || echo "no rollout recorded"
  ;;
*)
  usage
  ;;
esac
