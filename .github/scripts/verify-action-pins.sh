#!/usr/bin/env bash
# Verify that every action referenced under .github/workflows is pinned to a full
# commit SHA, carries a "# vX.Y.Z" version comment, and that the tag named in the
# comment resolves to exactly that commit in the action's own repository.
#
#   .github/scripts/verify-action-pins.sh [workflow-dir]
#
# Needs an authenticated gh (GH_TOKEN in CI). Exits non-zero on any unpinned
# reference, missing comment, unknown tag or mismatch, and also when it finds no
# references at all, so an empty or misread directory cannot pass.
set -euo pipefail

dir=${1:-.github/workflows}
fail=0
checked=0
tab=$(printf '\t')

# Print the commit a tag points to, dereferencing annotated tags.
resolve_tag() {
  local repo=$1 tag=$2 out type sha
  out=$(gh api "repos/$repo/git/ref/tags/$tag" --jq '[.object.type, .object.sha] | @tsv') || return 1
  type=${out%%"$tab"*}
  sha=${out##*"$tab"}
  while [ "$type" = tag ]; do
    out=$(gh api "repos/$repo/git/tags/$sha" --jq '[.object.type, .object.sha] | @tsv') || return 1
    type=${out%%"$tab"*}
    sha=${out##*"$tab"}
  done
  printf '%s\n' "$sha"
}

re='uses:[[:space:]]*([^[:space:]@#]+)@([^[:space:]#]+)[[:space:]]*(#[[:space:]]*([^[:space:]]+))?'

while IFS= read -r hit; do
  file=${hit%%:*}
  rest=${hit#*:}
  line=${rest%%:*}
  text=${rest#*:}
  [[ $text =~ $re ]] || continue
  action=${BASH_REMATCH[1]}
  ref=${BASH_REMATCH[2]}
  tag=${BASH_REMATCH[4]:-}
  case $action in ./* | docker://*) continue ;; esac
  repo=$(cut -d/ -f1-2 <<<"$action")
  where="$file:$line $action"
  checked=$((checked + 1))
  if ! [[ $ref =~ ^[0-9a-f]{40}$ ]]; then
    echo "FAIL $where: ref '$ref' is not a full commit SHA"
    fail=1
    continue
  fi
  if [ -z "$tag" ]; then
    echo "FAIL $where: no version comment after the SHA"
    fail=1
    continue
  fi
  if ! want=$(resolve_tag "$repo" "$tag"); then
    echo "FAIL $where: tag $tag not found in $repo"
    fail=1
    continue
  fi
  if [ "$want" != "$ref" ]; then
    echo "FAIL $where: $tag is $want, but the pin is $ref"
    fail=1
    continue
  fi
  echo "ok   $where $tag = $ref"
done < <(grep -rn -E '^[[:space:]]*-?[[:space:]]*uses:' "$dir")

echo "checked $checked pinned action reference(s) under $dir"
if [ "$checked" -eq 0 ]; then
  echo "FAIL no action references found under $dir"
  exit 1
fi
exit "$fail"
