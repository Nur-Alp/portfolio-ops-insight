import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// package.json's test/test:watch scripts set
// NODE_OPTIONS=--no-experimental-webstorage - without it, Node's own
// (non-functional without --localstorage-file) global `localStorage`
// already exists on globalThis by the time jsdom's environment sets up, and
// vitest's populateGlobal only copies a jsdom window property over an
// existing global one if that key is on its own curated allowlist (which
// `localStorage` isn't) - so window.localStorage silently stays undefined
// instead of jsdom's real, working implementation. sessionStorage has no
// such Node builtin, which is why only localStorage was ever affected.

const LANGUAGE_STORAGE_KEY = "osip-dashboard-language";

// The app defaults to Russian on first boot (no stored preference) - most of
// the test suite was written against the previous English default and
// asserts English strings throughout. Default every test's session to
// English here, once, globally, rather than rewriting each assertion - a
// test that needs Russian still wins by setting its own preference before
// rendering, since this only fills in when nothing has been set yet. This
// key must match i18n/index.tsx's STORAGE_KEY exactly.
beforeEach(() => {
  if (window.sessionStorage.getItem(LANGUAGE_STORAGE_KEY) === null) {
    window.sessionStorage.setItem(LANGUAGE_STORAGE_KEY, "en");
  }
});
