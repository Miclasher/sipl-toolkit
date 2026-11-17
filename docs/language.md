# The SIPL language as implemented

This document fixes the concrete syntax and semantics implemented by the toolkit. The
textbook gives an abstract BNF that is ambiguous as written; every choice made to remove
the ambiguity, and every extension, is listed here. The machine-readable grammar is
`grammar/sipl.lark`; the rule mapping is in `grammar/README.md`.

## BNF in course notation

```
P ::= begin S end                                   (P1)
S ::= x := a                                        (S1)
    | S1 ; S2                                       (S2)
    | if b then S1 else S2                          (S3)
    | while b do S                                  (S4)
    | begin S end                                   (S5)
    | skip                                          (S6)
a ::= n | x | a1 + a2 | a1 - a2 | a1 * a2 | (a)     (A1 .. A6)
    | a1 div a2                                    (A7, extension)
b ::= a1 = a2 | a1 > a2 | b1 ∨ b2 | ¬ b | (b)       (B1 .. B5)
```

`n` is an integer literal, `x` an identifier. The semantic rules of the textbook are named
NP1 (program), NS1-NS6 (statements), NA1-NA6 (arithmetic), NB1-NB5 (conditions) after the
syntactic rules above; the interpreter's structure mirrors them (see `docs/defense.md`).

## Concrete syntax

### Tokens

| Token | Form |
|---|---|
| Keywords | `begin end if then else while do skip or not`, reserved, matched as whole words |
| Identifier | ASCII letter, then letters, digits or `_` (`X`, `Count`, `x_1`) |
| Integer | one or more decimal digits; a leading `-` makes a negative literal (see below) |
| Operators | `:=  ;  +  -  *  =  >  (  )` |
| Logical | `or` or `∨`; `not` or `¬` |
| Whitespace | spaces, tabs, newlines; insignificant |
| Comment | `#` to end of line, ignored |

`begin_x` and `endx` are identifiers, not keywords. A program must contain at least one
statement; an empty `begin end` and a file consisting only of a comment are syntax errors.

### Extensions to the textbook BNF

- **`a1 div a2`** (A7): integer division, same precedence as `*`, left-associative. It is
  floor division (`-7 div 2 = -4`), which equals the usual `div` on naturals. `div` is a
  reserved word. Division by zero makes the function undefined: runtime error
  `division-by-zero` at the span of the divisor, exit code 2.

1. **Identifiers.** The textbook uses single capital letters (M, N, R, X, Y). Any identifier
   of the form above is accepted.
2. **`or` / `not` aliases.** `∨` and `¬` are the canonical symbols; the ASCII words `or`
   and `not` are interchangeable with them so programs can be typed on any keyboard.
3. **Comments.** `#` line comments are handled by the lexer only; they do not exist in the
   AST.
4. **Negative literals.** `-3` is a literal where an operand is expected.

### Precedence and associativity decisions

| Decision | Rationale |
|---|---|
| `*` binds tighter than `+` and `-` | usual arithmetic reading of A3-A5 |
| `+`, `-`, `*` are left-associative: `1 - 2 - 3` = `(1 - 2) - 3` | usual reading, matters for `-` |
| `=` and `>` take arithmetic operands on both sides; comparisons do not chain (`a = b = c` is a syntax error) | B1/B2 have `a` operands only |
| `not` binds tighter than `or`; `not a = b` means `not (a = b)` | usual reading of B3/B4 |
| `or` is left-associative | B3 |
| there is no `and` | not in the textbook BNF |
| `;` separates statements; `S1 ; S2 ; S3` is flattened into one `Seq` node with three items | semantically `;` is associative, flattening gives a simpler tree and a flat trace |
| a `;` needs a statement on both sides: `begin X := 1; end` is a syntax error | S2 is binary |
| `if` always has `else` (`skip` is the empty branch) | S3 has two branches; no dangling-else |
| the bodies of `then`, `else` and `do` are a single statement; `while c do a; b` parses as `(while c do a); b` | group with `begin ... end` (S5) |
| after a complete operand `-` is subtraction: `a - 1`, `a -1` and `a-1` are the same | disambiguates negative literals |
| unary minus on non-literals (`-x`) is not supported | not in the textbook; write `0 - x` |
| parentheses are kept in the AST as `ParenA` / `ParenB` | A6/B5 are rules of their own; spans stay exact |

Example of the `;` and `while` decisions:

```
begin
  while Y > 0 do Y := Y - 1;   # the loop body is only `Y := Y - 1`
  Z := 1                       # runs after the loop
end
```

## Semantics

SIPL is given the textbook's nominative-state semantics in executable form.

### State

A state is a **partial** map from variable names to integers. Integers are unbounded (Python
`int`); there is no overflow. The initial state is supplied by the user (`--var X=5`,
`inputs` in a debugger launch configuration) and is empty otherwise. The final state, which
includes the inputs, is the result of a run (e.g. the `power` example ends with `X = 5`,
`Y = 0`, `R = 25`).

### Statements (NS1-NS6)

| Statement | Effect |
|---|---|
| `x := a` | evaluate `a` in the current state, then bind `x` to the value (defined or redefined) |
| `S1 ; S2` | run `S1`, then run `S2` in the state produced by `S1` |
| `if b then S1 else S2` | evaluate `b`; run `S1` if true, `S2` if false |
| `while b do S` | evaluate `b`; if true run `S` and repeat; if false stop |
| `begin S end` | run `S` |
| `skip` | no effect |

### Expressions (NA, NB)

- `n` evaluates to itself, `x` to its value in the state, `a1 op a2` applies `+`, `-` or
  `*` to the values of both operands, `(a)` is `a`.
- `a1 = a2` and `a1 > a2` compare the integer values.
- `b1 or b2` is the logical disjunction. **Both operands are always evaluated** (total
  evaluation, no short-circuit), so an undefined variable in the right operand is an error
  even if the left operand is true. This matches the textbook's total predicates.
- `not b` is negation.

### Undefined variables

Reading a variable that has no value in the current state is a runtime error with code
`undefined-variable`, reported at the span of the offending occurrence, e.g.
`examples/invalid/undefined_var.sipl:3:8: runtime error: variable 'Y' is not defined`.
Execution stops, the state at that moment and the step count are reported, the CLI exits
with code 2, and the debugger stops with reason `exception`. Assigning to a variable that
does not exist yet is fine (that is how results such as `R` are created). The trace event
`variable_changed` carries `old = null` in that case.

### Step limit and step counting

Programs may not terminate, so execution is bounded by `--max-steps` (default 100 000;
`maxSteps` in the debugger). A **step** is counted for:

- each `Assign`, `Skip`, `If`, and `While` statement when it is entered;
- each additional evaluation of a `While` condition after the first one (the first check is
  part of entering the `While` step).

`Seq` and `Block` are structural and cost nothing. Examples: `power` with `X=5, Y=2` takes 8
steps (the initial assignment, the loop entry, 2 iterations of 2 assignments, and 2 further
condition checks); with `Y=1` it takes 5.

When the next step would exceed the limit, execution stops with the error
`step-limit-exceeded` (CLI exit code 2, span of the statement, or of the `While` whose next condition check, would have run). The
partial state and the counted steps are reported. The limit never causes a hang and never
raises a Python exception.

### Errors at a glance

| Code | Phase | Meaning |
|---|---|---|
| `syntax-error`, `unexpected-token`, `unexpected-character`, `unexpected-eof` | parse | message names what was found and what was expected; line/column attached |
| `undefined-variable` | run | read of an unassigned variable |
| `division-by-zero` | run | `a div 0` |
| `step-limit-exceeded` | run | the step budget was exhausted |
| `io-error` | CLI | input file unreadable |
