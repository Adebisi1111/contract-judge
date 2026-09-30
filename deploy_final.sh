#!/bin/bash
set -e
PROJECT="/home/administrator/contract-judge"

echo "=== 1. Build on main ==="
cd "$PROJECT"
git checkout main --quiet
npm run build 2>&1 | tail -3

echo "=== 2. Verify build ==="
ls -la dist/
ls -la dist/assets/
ls dist/index.html

echo "=== 3. Copy build to temp ==="
rm -rf /tmp/cj-build
mkdir -p /tmp/cj-build
cp -r dist/* /tmp/cj-build/
ls -la /tmp/cj-build/

echo "=== 4. Switch to gh-pages ==="
git checkout gh-pages --quiet
git reset --hard origin/gh-pages --quiet

echo "=== 5. Wipe and replace ==="
rm -rf assets/ index.html dist/ node_modules/ _trigger*
cp -r /tmp/cj-build/* .

echo "=== 6. Commit and push ==="
git add -A
git status --short
git commit -m "Deploy: ContractJudge frontend — on-chain verified" --quiet
git push origin gh-pages --force --quiet

echo "=== 7. Verify ==="
git ls-tree -r HEAD --name-only

echo "=== DONE ==="
