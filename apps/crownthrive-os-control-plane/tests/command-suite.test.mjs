// The canonical app validator discovers .test.mjs files.
// Import the CommonJS suite so the same 24 security/API cases run in release CI.
import './command-suite.test.cjs';
