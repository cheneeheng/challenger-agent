#!/usr/bin/env bash
# Deployment script tests — validates script syntax and required-variable checks
# without actually calling AWS CLI or Docker.
#
# Run: bash deploy/tests/test_deploy_scripts.sh
#
# Exit 0 = all tests passed; exit 1 = at least one failure.

set -euo pipefail

PASS=0
FAIL=0
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ok() {
  echo "  PASS: $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "  FAIL: $1"
  FAIL=$((FAIL + 1))
}

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$actual" = "$expected" ]; then
    ok "$desc"
  else
    fail "$desc (expected '$expected', got '$actual')"
  fi
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if echo "$haystack" | grep -q "$needle"; then
    ok "$desc"
  else
    fail "$desc (expected to find '$needle')"
  fi
}

# ---------------------------------------------------------------------------
# 1. Syntax check — bash -n validates all scripts without executing them
# ---------------------------------------------------------------------------

echo "=== Syntax checks ==="

for script in \
  "$REPO_ROOT/deploy/aws/deploy.sh" \
  "$REPO_ROOT/deploy/aws/setup-infra.sh" \
  "$REPO_ROOT/deploy/gcp/deploy.sh" \
  "$REPO_ROOT/deploy/azure/deploy.sh"
do
  name="${script#"$REPO_ROOT/"}"
  if bash -n "$script" 2>/dev/null; then
    ok "syntax: $name"
  else
    fail "syntax: $name"
  fi
done

# ---------------------------------------------------------------------------
# 2. Required-variable enforcement in deploy.sh
# Calling the script with no env vars set should fail on the first :? check.
# We stub out git and any sourced .env to isolate the variable test.
# ---------------------------------------------------------------------------

echo ""
echo "=== Required variable enforcement (deploy.sh) ==="

DEPLOY_SCRIPT="$REPO_ROOT/deploy/aws/deploy.sh"

# Helper: runs deploy.sh in a clean env; captures stderr; returns exit code.
run_deploy_no_env() {
  env -i HOME=/tmp PATH="$PATH" \
    bash -c "
      # Stub git so the script doesn't fail on rev-parse before the :? checks
      git() {
        case \"\$*\" in
          'rev-parse --show-toplevel') echo '/tmp' ;;
          'rev-parse --short HEAD')   echo 'abc1234' ;;
          *) command git \"\$@\" ;;
        esac
      }
      export -f git
      source '$DEPLOY_SCRIPT'
    " 2>&1 || true
}

output=$(run_deploy_no_env)
assert_contains "missing APP_NAME → error message"        "APP_NAME"          "$output"

# With APP_NAME set but rest missing
output2=$(env -i HOME=/tmp PATH="$PATH" APP_NAME="myapp" \
  bash -c "
    git() {
      case \"\$*\" in
        'rev-parse --show-toplevel') echo '/tmp' ;;
        'rev-parse --short HEAD')   echo 'abc1234' ;;
      esac
    }
    export -f git
    source '$DEPLOY_SCRIPT'
  " 2>&1 || true)
assert_contains "missing APPRUNNER_ECR_ROLE_ARN → error message" "APPRUNNER_ECR_ROLE_ARN" "$output2"

# ---------------------------------------------------------------------------
# 3. Required-variable enforcement in setup-infra.sh
# ---------------------------------------------------------------------------

echo ""
echo "=== Required variable enforcement (setup-infra.sh) ==="

SETUP_SCRIPT="$REPO_ROOT/deploy/aws/setup-infra.sh"

output3=$(env -i HOME=/tmp PATH="$PATH" \
  bash -c "
    git() {
      case \"\$*\" in
        'rev-parse --show-toplevel') echo '/tmp' ;;
      esac
    }
    export -f git
    source '$SETUP_SCRIPT'
  " 2>&1 || true)
assert_contains "missing APP_NAME → error in setup-infra" "APP_NAME" "$output3"

# ---------------------------------------------------------------------------
# 4. Dockerfile frontend has PUBLIC_API_URL ARG + ENV
# ---------------------------------------------------------------------------

echo ""
echo "=== Dockerfile.frontend PUBLIC_API_URL ==="

dockerfile="$REPO_ROOT/infra/Dockerfile.frontend"
if [ -f "$dockerfile" ]; then
  content=$(cat "$dockerfile")
  assert_contains "Dockerfile.frontend has ARG PUBLIC_API_URL" "ARG PUBLIC_API_URL" "$content"
  assert_contains "Dockerfile.frontend has ENV PUBLIC_API_URL" "ENV PUBLIC_API_URL" "$content"
else
  fail "Dockerfile.frontend not found"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

[ "$FAIL" -eq 0 ]
