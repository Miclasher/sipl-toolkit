# SIPL for VS Code

## Features
- Syntax highlighting, snippets, bracket/indent/folding rules for `.sipl` files.
- Debugging with F5: breakpoints, stepping, variables showing the actual program state.

## Requirements
Python 3.11+ and the toolkit: `pip install sipl-toolkit`. The extension runs `python -m sipl.dap`.

## Usage
Open a `.sipl` file and press F5 (no `launch.json` needed). Or add:

```json
{
  "type": "sipl",
  "request": "launch",
  "name": "Debug SIPL program",
  "program": "${file}",
  "inputs": { "X": 5, "Y": 2 },
  "maxSteps": 100000,
  "stopOnEntry": true
}
```

## Try from source
Open the `vscode-sipl` folder in VS Code and press F5 to start the Extension Host.

## Settings
| Setting | Default | Description |
|---|---|---|
| `sipl.pythonPath` | `python3` | Interpreter used to launch the adapter |
| `sipl.dapCommand` | unset | Array overriding the whole adapter command |

Launch property `pythonPath` overrides `sipl.pythonPath` per configuration.
