#!/usr/bin/env bash
#
# install_deps.sh -- install the pipeline's runtime dependencies where the
# pipeline runs (the Cowork Linux sandbox, or wherever bash is running this).
#
#     bash scripts/install_deps.sh
#
# Idempotent and quiet: every check is "already there?" before "install". Field
# result 2026-09-02: the sandbox ships Pillow and openpyxl but NOT PyMuPDF and
# NOT the docx Node package, and node resolves require('docx') only from a
# node_modules beside the script, never from a global install. So both halves
# are always needed on a fresh sandbox and this must run before smoke_test.sh.
#
# Python: requirements.txt beside this script. Tries a plain pip install first,
# then --break-system-packages (Debian/Ubuntu images refuse the plain form),
# then --user. Node: npm install in this directory, driven by package.json.
set -u
cd "$(dirname "$0")"

fail=0
ok()  { printf '  [OK]   %s\n' "$1"; }
bad() { printf '  [FAIL] %s\n' "$1"; fail=$((fail+1)); }

# Resolve the interpreter by running it, not by name: a Store stub called
# python3 exists on Windows hosts and fails when invoked.
PY=""
for cand in python3 python; do
    if "$cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "ERROR: no working python interpreter on PATH (tried python3, then python)." >&2
    exit 1
fi
echo "install_deps: python=$PY node=$(node --version 2>/dev/null || echo MISSING) cwd=$(pwd)"

# --- Python -----------------------------------------------------------------
need_py=""
for mod in pymupdf PIL openpyxl; do
    "$PY" -c "import $mod" >/dev/null 2>&1 || need_py="$need_py $mod"
done
if [ -z "$need_py" ]; then
    ok "python packages already present (pymupdf, pillow, openpyxl)"
else
    echo "  installing python packages for:$need_py"
    if ! "$PY" -m pip --version >/dev/null 2>&1; then
        bad "pip is not available for $PY; install pip or use a python that has it"
    elif "$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt >/dev/null 2>&1 \
      || "$PY" -m pip install --quiet --disable-pip-version-check --break-system-packages -r requirements.txt >/dev/null 2>&1 \
      || "$PY" -m pip install --quiet --disable-pip-version-check --user -r requirements.txt >/dev/null 2>&1; then
        ok "python packages installed from requirements.txt"
    else
        bad "pip install -r requirements.txt failed; run it by hand to see the error"
    fi
fi
for mod in pymupdf PIL openpyxl; do
    "$PY" -c "import $mod" >/dev/null 2>&1 && ok "import $mod" || bad "import $mod still fails"
done

# --- Node -------------------------------------------------------------------
if ! command -v node >/dev/null 2>&1; then
    bad "node is not on PATH; the renderer cannot run"
elif node -e 'require("docx")' >/dev/null 2>&1; then
    ok "docx package already present"
else
    echo "  installing node packages from package.json"
    if command -v npm >/dev/null 2>&1 && npm install --no-audit --no-fund --loglevel=error >/dev/null 2>&1; then
        ok "npm install completed"
    else
        bad "npm install failed; run 'npm install' in $(pwd) to see the error"
    fi
    node -e 'require("docx")' >/dev/null 2>&1 && ok "require('docx')" || bad "require('docx') still fails"
fi

echo
if [ "$fail" -gt 0 ]; then
    echo "$fail dependency step(s) FAILED"
    exit 1
fi
echo "all dependencies present"
