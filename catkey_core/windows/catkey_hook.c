/*
 * CatKey - Windows system-wide Telex/VNI hook engine.
 *
 * Installs a WH_KEYBOARD_LL hook. Buffers the current word (raw ASCII keys),
 * and on every relevant key recomputes the Vietnamese form and rewrites what
 * is on screen using synthetic Backspace + Unicode SendInput. This is how
 * UniKey/EVKey inject text into arbitrary apps (Notepad, browsers, etc.).
 *
 * Public C ABI (called from the Python UI via ctypes):
 *   int  catkey_start(void);
 *   void catkey_stop(void);
 *   void catkey_set_enabled(int on);
 *   void catkey_set_method(int method);   // 1=Telex, 2=VNI
 *   int  catkey_is_running(void);
 *
 * The message loop for the LL hook runs on a dedicated thread so the caller
 * (Python) does not need to pump messages.
 */

#ifdef _WIN32

#include <windows.h>
#include <string.h>
#include <ctype.h>

/* From vietnamese_tep.c */
int catkey_convert_word(const char *word, char *output, int max_len, int method);

#define CATKEY_TELEX 1
#define CATKEY_VNI   2
#define CATKEY_VIQR  3
#define CATKEY_TEIP_VNI 4
#define BUF_MAX      48

static HHOOK   g_hook = NULL;
static DWORD   g_thread_id = 0;
static HANDLE  g_thread = NULL;
static volatile LONG g_enabled = 1;
static volatile LONG g_method  = CATKEY_TELEX;

/* Toggle hotkey: a VK plus required modifier mask (1=Ctrl,2=Shift,4=Alt).
 * If g_toggle_vk == 0, the combo is "modifiers only" (g_toggle_mods must all
 * be held and one of them just pressed). We default to Ctrl+Shift. */
static volatile LONG g_toggle_vk   = 0;
static volatile LONG g_toggle_mods = 1 | 2;   /* Ctrl+Shift */
static volatile LONG g_toggled_state = 1;     /* mirrors g_enabled for polling */
static int g_combo_latch = 0;                 /* prevents repeat while held */

/* Restore hotkey: re-type the original (un-converted) word. vk=0 disables. */
static volatile LONG g_restore_vk   = 0;
static volatile LONG g_restore_mods = 1 | 2;  /* Ctrl+Shift by default */

/* Current word buffer: the raw keys the user typed (ASCII), plus the number
 * of on-screen characters we last produced (so we know how many to delete). */
static char g_raw[BUF_MAX];
static int  g_raw_len = 0;
static int  g_shown_units = 0;   /* # of UTF-16 code units currently on screen */

static int g_sending = 0;        /* re-entrancy guard while we SendInput */

static void reset_word(void) {
    g_raw_len = 0;
    g_shown_units = 0;
}

/* Count UTF-16 code units needed for a UTF-8 string (BMP chars = 1 unit;
 * all Vietnamese precomposed chars are BMP, so 1 unit each). */
static int utf16_units(const wchar_t *w) {
    int n = 0;
    while (w[n]) n++;
    return n;
}

/* UTF-16 units a single 1-byte char occupies on screen (1 for ASCII). */
static int char_units(char ch) {
    wchar_t w;
    int n = MultiByteToWideChar(CP_UTF8, 0, &ch, 1, &w, 1);
    return n > 0 ? n : 1;
}

/* Send `count` backspaces then the wide string `w`. */
static void rewrite(int backspaces, const wchar_t *w) {
    int wlen = utf16_units(w);
    int total = backspaces * 2 + wlen * 2;
    if (total <= 0) return;

    INPUT *in = (INPUT *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                                   sizeof(INPUT) * total);
    if (!in) return;
    int idx = 0;

    for (int i = 0; i < backspaces; i++) {
        in[idx].type = INPUT_KEYBOARD;
        in[idx].ki.wVk = VK_BACK;
        idx++;
        in[idx].type = INPUT_KEYBOARD;
        in[idx].ki.wVk = VK_BACK;
        in[idx].ki.dwFlags = KEYEVENTF_KEYUP;
        idx++;
    }
    for (int i = 0; i < wlen; i++) {
        in[idx].type = INPUT_KEYBOARD;
        in[idx].ki.wScan = w[i];
        in[idx].ki.dwFlags = KEYEVENTF_UNICODE;
        idx++;
        in[idx].type = INPUT_KEYBOARD;
        in[idx].ki.wScan = w[i];
        in[idx].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
        idx++;
    }

    g_sending = 1;
    SendInput(idx, in, sizeof(INPUT));
    g_sending = 0;
    HeapFree(GetProcessHeap(), 0, in);
}

/*
 * Recompute the current word. Decide whether the newly added key needs the
 * screen rewritten.
 *
 * Returns:
 *   0 -> converted output == the raw keys typed so far. The last key can be
 *        left to pass through normally (no doubling). Caller must NOT swallow.
 *   1 -> conversion differs (a diacritic applied). We rewrote the screen via
 *        backspace + Unicode SendInput. Caller MUST swallow the original key.
 *
 * g_shown_units always tracks how many UTF-16 units are currently on screen
 * for this word, whether they arrived via pass-through or via our SendInput.
 */
static int recompute_and_apply(int added_units) {
    if (g_raw_len == 0) return 0;
    g_raw[g_raw_len] = 0;

    char utf8[BUF_MAX * 4];
    int m = (int)InterlockedOr(&g_method, 0);
    int n = catkey_convert_word(g_raw, utf8, sizeof(utf8), m);
    if (n <= 0) { strcpy(utf8, g_raw); }

    /* If conversion equals the raw ASCII, nothing to do: let the key through. */
    if (strcmp(utf8, g_raw) == 0) {
        /* The OS will display exactly `added_units` code units for this key. */
        g_shown_units += (added_units > 0 ? added_units : 1);
        return 0;
    }

    wchar_t wbuf[BUF_MAX * 2];
    int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8, -1, wbuf, BUF_MAX * 2);
    if (wlen <= 0) { g_shown_units += (added_units > 0 ? added_units : 1); return 0; }
    wlen -= 1; /* exclude null */

    /* Rewrite: the original key hasn't been shown yet (we will swallow it),
     * so only delete what is currently on screen (g_shown_units). */
    rewrite(g_shown_units, wbuf);
    g_shown_units = wlen;
    return 1;
}

static LRESULT CALLBACK ll_proc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode != HC_ACTION || g_sending)
        return CallNextHookEx(g_hook, nCode, wParam, lParam);

    KBDLLHOOKSTRUCT *kb = (KBDLLHOOKSTRUCT *)lParam;

    DWORD vk = kb->vkCode;
    SHORT ctrl = GetAsyncKeyState(VK_CONTROL) & 0x8000;
    SHORT alt  = GetAsyncKeyState(VK_MENU) & 0x8000;
    SHORT shift= GetAsyncKeyState(VK_SHIFT) & 0x8000;
    SHORT win  = (GetAsyncKeyState(VK_LWIN) | GetAsyncKeyState(VK_RWIN)) & 0x8000;

    int is_down = (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN);
    int is_up   = (wParam == WM_KEYUP   || wParam == WM_SYSKEYUP);

    /* --- Global toggle hotkey (runs even when disabled) --- */
    LONG tvk = InterlockedOr(&g_toggle_vk, 0);
    LONG tmods = InterlockedOr(&g_toggle_mods, 0);
    int want_ctrl  = (tmods & 1) != 0;
    int want_shift = (tmods & 2) != 0;
    int want_alt   = (tmods & 4) != 0;
    if (is_down) {
        int mods_ok = (!want_ctrl  || ctrl) &&
                      (!want_shift || shift) &&
                      (!want_alt   || alt);
        int combo;
        if (tvk == 0) {
            /* modifiers-only combo: the just-pressed key must be one of the
             * required modifiers, and all required modifiers held. */
            int this_is_mod =
                (vk == VK_CONTROL || vk == VK_LCONTROL || vk == VK_RCONTROL ||
                 vk == VK_SHIFT   || vk == VK_LSHIFT   || vk == VK_RSHIFT   ||
                 vk == VK_MENU    || vk == VK_LMENU    || vk == VK_RMENU);
            combo = mods_ok && this_is_mod;
        } else {
            combo = mods_ok && (vk == (DWORD)tvk);
        }
        if (combo && !g_combo_latch) {
            g_combo_latch = 1;
            LONG cur = InterlockedOr(&g_enabled, 0);
            InterlockedExchange(&g_enabled, cur ? 0 : 1);
            InterlockedExchange(&g_toggled_state, cur ? 0 : 1);
            reset_word();
            /* for a plain modifier combo we let the key pass through */
            if (tvk != 0) return 1; /* swallow the hotkey key */
        }
    }
    if (is_up) {
        /* release latch when a required modifier is released */
        if (vk == VK_CONTROL || vk == VK_LCONTROL || vk == VK_RCONTROL ||
            vk == VK_SHIFT   || vk == VK_LSHIFT   || vk == VK_RSHIFT   ||
            vk == VK_MENU    || vk == VK_LMENU    || vk == VK_RMENU    ||
            (tvk != 0 && vk == (DWORD)tvk)) {
            g_combo_latch = 0;
        }
    }

    /* --- Restore hotkey: re-type the original (un-converted) word --- */
    /* Only meaningful while Vietnamese typing is enabled. */
    LONG rvk = InterlockedOr(&g_restore_vk, 0);
    if (rvk != 0 && is_down && g_raw_len > 0 && InterlockedOr(&g_enabled, 0)) {
        LONG rmods = InterlockedOr(&g_restore_mods, 0);
        int rmods_ok = ((rmods & 1) ? ctrl  : 1) &&
                       ((rmods & 2) ? shift : 1) &&
                       ((rmods & 4) ? alt   : 1);
        if (rmods_ok && vk == (DWORD)rvk) {
            /* Delete the converted word on screen, then type the raw ASCII. */
            wchar_t raw_w[BUF_MAX * 4];
            int ru = MultiByteToWideChar(CP_UTF8, 0, g_raw, g_raw_len, raw_w,
                                         BUF_MAX * 4 - 1);
            raw_w[ru] = 0;
            rewrite(g_shown_units, raw_w);
            reset_word();
            return 1; /* swallow the hotkey key */
        }
    }

    /* If disabled, do nothing further (pass everything through). */
    if (!InterlockedOr(&g_enabled, 0))
        return CallNextHookEx(g_hook, nCode, wParam, lParam);

    if (!is_down)
        return CallNextHookEx(g_hook, nCode, wParam, lParam);

    /* modifiers held? -> flush and pass through (Ctrl/Alt/Win shortcuts) */
    if (ctrl || alt || win) {
        reset_word();
        return CallNextHookEx(g_hook, nCode, wParam, lParam);
    }

    /* Backspace: shrink our buffer and let it pass. */
    if (vk == VK_BACK) {
        if (g_raw_len > 0) g_raw_len--;
        if (g_shown_units > 0) g_shown_units--;
        return CallNextHookEx(g_hook, nCode, wParam, lParam);
    }

    /* Word separators: commit and reset. */
    if (vk == VK_SPACE || vk == VK_RETURN || vk == VK_TAB ||
        vk == VK_ESCAPE || (vk >= VK_LEFT && vk <= VK_DOWN) ||
        vk == VK_HOME || vk == VK_END || vk == VK_DELETE) {
        reset_word();
        return CallNextHookEx(g_hook, nCode, wParam, lParam);
    }

    /* Map VK to an ASCII character (letters + digits + a few marks).
     * Letter case = Shift XOR CapsLock (CapsLock only affects letters). */
    char ch = 0;
    int caps = (GetKeyState(VK_CAPITAL) & 1) ? 1 : 0;

    /* VIQR mode: buffer diacritic punctuation instead of committing.
     * Must be checked BEFORE the digit-with-shift path since Shift+6 (^),
     * Shift+9 ((), etc. are shifted digits. */
    if ((int)InterlockedOr(&g_method, 0) == CATKEY_VIQR) {
        char viqr_ch = 0;
        if      (vk == 0xDE && !shift) viqr_ch = '\'';  /* ' sac */
        else if (vk == 0xC0 && !shift) viqr_ch = '`';   /* ` huyen */
        else if (vk == 0xBF &&  shift) viqr_ch = '?';   /* ? hoi  */
        else if (vk == 0xC0 &&  shift) viqr_ch = '~';   /* ~ nga  */
        else if (vk == 0xBE && !shift) viqr_ch = '.';   /* . nang */
        else if (vk == '6'  &&  shift) viqr_ch = '^';   /* ^ circumflex */
        else if (vk == '9'  &&  shift) viqr_ch = '(';   /* ( breve */
        else if (vk == 0xBB &&  shift) viqr_ch = '+';   /* + horn */
        if (viqr_ch) {
            if (g_raw_len >= BUF_MAX - 1) reset_word();
            g_raw[g_raw_len++] = viqr_ch;
            if (recompute_and_apply(char_units(viqr_ch)))
                return 1;
            return CallNextHookEx(g_hook, nCode, wParam, lParam);
        }
    }

    if (vk >= 'A' && vk <= 'Z') {
        int upper = (shift ? 1 : 0) ^ caps;
        ch = (char)(upper ? vk : (vk | 0x20));
    } else if (vk >= '0' && vk <= '9') {
        int sh = shift ? 1 : 0;
        if (sh) { reset_word(); return CallNextHookEx(g_hook, nCode, wParam, lParam); }
        ch = (char)vk;
    } else {
        /* punctuation etc: commit current word, pass through */
        reset_word();
        return CallNextHookEx(g_hook, nCode, wParam, lParam);
    }

    if (g_raw_len >= BUF_MAX - 1) reset_word();

    /* Add the raw key and convert. If the conversion is unchanged we let the
     * original key pass through (avoids doubling). If a diacritic applied we
     * rewrote the screen ourselves, so swallow the original key. */
    g_raw[g_raw_len++] = ch;
    if (recompute_and_apply(char_units(ch)))
        return 1;  /* swallowed: we already emitted the corrected word */
    return CallNextHookEx(g_hook, nCode, wParam, lParam); /* pass through */
}

static DWORD WINAPI hook_thread(LPVOID param) {
    (void)param;
    g_hook = SetWindowsHookExW(WH_KEYBOARD_LL, ll_proc, GetModuleHandleW(NULL), 0);
    if (!g_hook) return 1;

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        if (msg.message == WM_QUIT) break;
    }
    UnhookWindowsHookEx(g_hook);
    g_hook = NULL;
    return 0;
}

__declspec(dllexport) int catkey_start(void) {
    if (g_thread) return 1; /* already running */
    reset_word();
    g_thread = CreateThread(NULL, 0, hook_thread, NULL, 0, &g_thread_id);
    return g_thread != NULL;
}

__declspec(dllexport) void catkey_stop(void) {
    if (g_thread_id) PostThreadMessageW(g_thread_id, WM_QUIT, 0, 0);
    if (g_thread) {
        WaitForSingleObject(g_thread, 2000);
        CloseHandle(g_thread);
        g_thread = NULL;
        g_thread_id = 0;
    }
    reset_word();
}

__declspec(dllexport) void catkey_set_enabled(int on) {
    InterlockedExchange(&g_enabled, on ? 1 : 0);
    InterlockedExchange(&g_toggled_state, on ? 1 : 0);
    reset_word();
}

__declspec(dllexport) int catkey_get_enabled(void) {
    return (int)InterlockedOr(&g_enabled, 0);
}

__declspec(dllexport) void catkey_set_method(int method) {
    if (method == CATKEY_VNI || method == CATKEY_VIQR || method == CATKEY_TEIP_VNI)
        InterlockedExchange(&g_method, method);
    else
        InterlockedExchange(&g_method, CATKEY_TELEX);
    reset_word();
}

/* Configure the global toggle hotkey.
 * vk=0 means "modifiers only" (mods mask: 1=Ctrl,2=Shift,4=Alt). */
__declspec(dllexport) void catkey_set_toggle_key(int vk, int mods) {
    InterlockedExchange(&g_toggle_vk, vk);
    InterlockedExchange(&g_toggle_mods, mods);
}

/* Configure the restore-original-word hotkey. vk=0 disables it. */
__declspec(dllexport) void catkey_set_restore_key(int vk, int mods) {
    InterlockedExchange(&g_restore_vk, vk);
    InterlockedExchange(&g_restore_mods, mods);
}

__declspec(dllexport) int catkey_is_running(void) {
    return g_thread != NULL;
}

#endif /* _WIN32 */
