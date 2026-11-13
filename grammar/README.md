# SIPL grammar

`sipl.lark` is a Lark LALR(1) grammar. `src/sipl/parser.py` loads it (installed
`sipl/sipl.lark` first, then `grammar/sipl.lark` in the source tree) and builds
`sipl.ast` nodes with exact source spans. Start symbols: `program`, `aexp`, `bexp`.

## Rule mapping (textbook BNF)

| Textbook | Grammar rule | AST node |
|---|---|---|
| P1 `begin S end` | `program` | `Program` |
| S1 `x := a` | `assign` | `Assign` |
| S2 `S1 ; S2` | `seq` (`stmt (SEMI stmt)*`) | `Seq` (flat, >= 2 items) |
| S3 `if b then S1 else S2` | `ifstmt` | `If` |
| S4 `while b do S` | `whilestmt` | `While` |
| S5 `begin S end` | `block` | `Block` |
| S6 `skip` | `skip` | `Skip` |
| A1 `n` | `atom` -> `num` / `neg` | `Num` |
| A2 `x` | `atom` -> `var` | `Var` |
| A3 `a1 + a2` | `aexp` -> `add` | `BinOp("+")` |
| A4 `a1 - a2` | `aexp` -> `sub` | `BinOp("-")` |
| A5 `a1 * a2` | `term` -> `mul` | `BinOp("*")` |
| A6 `(a)` | `atom` -> `parena` | `ParenA` |
| B1 `a1 = a2` | `batom` -> `eq` | `Cmp("=")` |
| B2 `a1 > a2` | `batom` -> `gt` | `Cmp(">")` |
| B3 `b1 or b2` | `bexp` -> `or_` | `Or` |
| B4 `not b` | `bterm` -> `not_` | `Not` |
| B5 `(b)` | `batom` -> `parenb` | `ParenB` |

## Ambiguity resolutions

- `*` binds tighter than `+`/`-`; all binary arithmetic operators are left-associative
  (`1 - 2 - 3` = `(1 - 2) - 3`).
- `not`/`¬` binds tighter than `or`/`∨`; `or` is left-associative.
  Comparisons take arithmetic operands only (`a = b = c` is a syntax error).
- `;` is right-associative in the textbook; here it is flattened into one `Seq`.
  A single statement is not wrapped. A trailing or leading `;` is a syntax error.
- `if` always has `else` (no dangling-else ambiguity). `then`/`else`/`do` bodies are a single
  statement; use `begin ... end` to group (`while c do a; b` parses as `(while c do a); b`).
- Keywords `begin end if then else while do skip or not` are reserved, matched as whole words
  (`begin_x` and `endx` are identifiers). Identifiers: ASCII letter, then letters/digits/`_`.
- Integer literals are digits. `-n` is a negative literal `Num(-n)` only where an operand is
  expected; after a complete operand `-` is subtraction, so `a - 1`, `a -1` and `a-1` are equal.
  Unary minus on non-literals (`-x`) is not supported.
- `∨`/`or` and `¬`/`not` are interchangeable. `#` starts a line comment.
