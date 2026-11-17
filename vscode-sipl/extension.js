'use strict';
const vscode = require('vscode');

const INSTALL_HINT = 'Install with: git clone + pip install';

async function pythonFromExtension() {
  try {
    const ext = vscode.extensions.getExtension('ms-python.python');
    if (!ext) return undefined;
    const api = ext.isActive ? ext.exports : await ext.activate();
    const p = api && api.settings && api.settings.getExecutionDetails
      ? api.settings.getExecutionDetails().execCommand
      : undefined;
    return Array.isArray(p) && p.length ? p[0] : undefined;
  } catch (e) {
    return undefined;
  }
}

class SiplAdapterFactory {
  async createDebugAdapterDescriptor(session) {
    const cfg = vscode.workspace.getConfiguration('sipl');
    const cmd = cfg.get('dapCommand');
    if (Array.isArray(cmd) && cmd.length > 0) {
      return new vscode.DebugAdapterExecutable(cmd[0], cmd.slice(1));
    }
    let python = session && session.configuration && session.configuration.pythonPath;
    if (!python) {
      const setting = cfg.get('pythonPath');
      const inspected = cfg.inspect ? cfg.inspect('pythonPath') : undefined;
      const explicit = inspected && (inspected.globalValue || inspected.workspaceValue || inspected.workspaceFolderValue);
      python = explicit ? setting : (await pythonFromExtension()) || setting || 'python3';
    }
    return new vscode.DebugAdapterExecutable(python, ['-m', 'sipl.dap']);
  }
}

class SiplConfigProvider {
  resolveDebugConfiguration(folder, config) {
    if (!config.type && !config.request && !config.name) {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.languageId !== 'sipl') {
        vscode.window.showErrorMessage('Open a .sipl file to debug it.');
        return null;
      }
      config.type = 'sipl';
      config.request = 'launch';
      config.name = 'Debug SIPL program';
      config.program = editor.document.fileName;
      config.stopOnEntry = true;
      config.inputs = {};
    }
    if (!config.program) {
      config.program = '${file}';
    }
    return config;
  }
}

function activate(context) {
  context.subscriptions.push(
    vscode.debug.registerDebugAdapterDescriptorFactory('sipl', new SiplAdapterFactory()),
    vscode.debug.registerDebugConfigurationProvider('sipl', new SiplConfigProvider())
  );
  if (vscode.debug.registerDebugAdapterTrackerFactory) {
    context.subscriptions.push(vscode.debug.registerDebugAdapterTrackerFactory('sipl', {
      createDebugAdapterTracker() {
        return {
          onError(err) {
            vscode.window.showErrorMessage('SIPL debug adapter failed: ' + (err && err.message) + '. ' + INSTALL_HINT);
          },
          onExit(code) {
            if (code) {
              vscode.window.showErrorMessage('SIPL debug adapter exited with code ' + code + '. Is Python 3.11+ available and sipl-toolkit installed? ' + INSTALL_HINT);
            }
          }
        };
      }
    }));
  }
}

function deactivate() {}

module.exports = { activate, deactivate };
