"""Syntax-check all .py files in the project."""
import ast, os, sys

root = r"e:\Personal\Group Assignments\Tiếng Anh chuyên ngành\Lần học 2\Project_60%"
ok = 0
fail = 0
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith(".py") or f == "verify_syntax.py":
            continue
        full = os.path.join(dp, f)
        rel = os.path.relpath(full, root)
        try:
            with open(full, encoding="utf-8") as fh:
                ast.parse(fh.read())
            print(f"  OK : {rel}")
            ok += 1
        except SyntaxError as e:
            print(f"  FAIL: {rel} -> {e}")
            fail += 1

print(f"\nTotal: {ok} OK, {fail} FAIL")
sys.exit(fail)
