// What this device remembers about logging in (SPEC F02 rules 1 and 2, D-182):
// the last school code (so /login goes straight to the school's page), the tab
// used last on that page, and whether the last login was the platform's. Never
// a name, username or password. Like a WordPress "remember me" cookie, but only
// for the page, not the account. Storage can be missing (private windows), so
// every read and write is guarded and the pages work without it.

const CODE_KEY = "sf:school-code";
const TAB_KEY = "sf:login-tab";
const PLATFORM_KEY = "sf:platform";
// The school whose page was used, for this browser tab only: a parent of
// several schools starts there (sent as X-School-Id).
const SCHOOL_ID_KEY = "sf:school-id";

export type LoginTab = "staff" | "student";

function read(store: () => Storage, key: string): string | null {
  try {
    return store().getItem(key);
  } catch {
    return null;
  }
}

function write(store: () => Storage, key: string, value: string | null): void {
  try {
    if (value === null) store().removeItem(key);
    else store().setItem(key, value);
  } catch {
    // Storage is off: the pages still work, they just don't remember.
  }
}

const local = () => window.localStorage;
const session = () => window.sessionStorage;

export function rememberedCode(): string | null {
  const code = read(local, CODE_KEY);
  return code && /^[A-Z0-9]{3,10}$/.test(code) ? code : null;
}

export function rememberCode(code: string): void {
  write(local, CODE_KEY, code.toUpperCase());
  write(local, PLATFORM_KEY, null);
}

export function forgetCode(): void {
  write(local, CODE_KEY, null);
}

export function rememberedTab(): LoginTab {
  return read(local, TAB_KEY) === "staff" ? "staff" : "student";
}

export function rememberTab(tab: LoginTab): void {
  write(local, TAB_KEY, tab);
}

export function rememberPlatform(): void {
  write(local, PLATFORM_KEY, "1");
}

export function usedPlatform(): boolean {
  return read(local, PLATFORM_KEY) === "1";
}

export function chosenSchoolId(): string | null {
  return read(session, SCHOOL_ID_KEY);
}

export function chooseSchoolId(id: string | null): void {
  write(session, SCHOOL_ID_KEY, id);
}

// Where to log in again after signing out or a session ending (F02 rule 2).
export function loginPage(): string {
  if (usedPlatform()) return "/platform/login";
  const code = rememberedCode();
  return code ? `/login/${code}` : "/login";
}
