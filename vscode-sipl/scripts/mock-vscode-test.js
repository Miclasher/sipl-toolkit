'use strict';
const Module = require('module');
const path = require('path');
const assert = require('assert');
let factory;
let settings = {};
class DebugAdapterExecutable { constructor(command, args) { this.command = command; this.args = args; } }
const vscode = {
  DebugAdapterExecutable,
  debug: {
    registerDebugAdapterDescriptorFactory: (t, f) => { assert.strictEqual(t, 'sipl'); factory = f; return { dispose() {} }; },
    registerDebugConfigurationProvider: () => ({ dispose() {} })
  },
  workspace: { getConfiguration: () => ({ get: (k) => settings[k], inspect: (k) => ({ globalValue: settings[k] }) }) },
  extensions: { getExtension: () => undefined },
  window: { showErrorMessage() {}, activeTextEditor: undefined }
};
const orig = Module._load;
Module._load = function (req, ...rest) { return req === 'vscode' ? vscode : orig.call(this, req, ...rest); };
const ext = require(path.join(__dirname, '..', 'extension.js'));
const ctx = { subscriptions: [] };
ext.activate(ctx);
assert.ok(factory, 'factory registered');
(async () => {
  const d = await factory.createDebugAdapterDescriptor({ configuration: {} });
  assert.ok(d instanceof DebugAdapterExecutable);
  assert.deepStrictEqual(d.args, ['-m', 'sipl.dap']);
  assert.strictEqual(d.command, 'python3');
  settings = { pythonPath: 'py', dapCommand: ['x', 'a'] };
  const d2 = await factory.createDebugAdapterDescriptor({ configuration: {} });
  assert.deepStrictEqual([d2.command, d2.args], ['x', ['a']]);
  console.log('mock-vscode-test: OK');
})().catch((e) => { console.error(e); process.exit(1); });
