/*
 * CatKey - Vietnamese Input Method
 * Telex / VNI conversion engine (word-level).
 *
 * TEMPORARY working engine. Handles the common cases:
 *   Telex marks:  aa->a^, aw->a(, ee->e^, oo->o^, ow->o+, uw->u+, dd->d-
 *   Telex tones:  s(sac) f(huyen) r(hoi) x(nga) j(nang) z(remove)
 *   VNI:          1..5 tones, 6/7/8 marks, 9 for d->đ
 *
 * Tones/marks apply to the correct vowel of the syllable. Output is UTF-8
 * precomposed Vietnamese. Extend later for full spelling rules.
 */

#include <stdint.h>
#include <string.h>
#include <ctype.h>

#define CATKEY_TEIP 1
#define CATKEY_VNI 2
#define CATKEY_VIQR 3
#define MAX_OUTPUT_LENGTH 64

/* Tone indices */
enum { T_NONE = 0, T_SAC, T_HUYEN, T_HOI, T_NGA, T_NANG };

/* Base vowel identity: letter + variant (0=plain,1=circumflex ^,2=breve/horn) */
typedef struct {
    char base;    /* a e i o u y */
    int  variant; /* 0 plain, 1 ^ (a^ e^ o^), 2 ( for a, + for o/u */
    int  tone;    /* T_* */
    int  upper;   /* capitalisation */
} Vowel;

/* Precomposed UTF-8 tables indexed [variant][tone] for each base vowel.
 * Only the combinations Vietnamese actually uses are filled. */

/* a, â (a1), ă (a2) */
static const char *A_[3][6] = {
    {"a","\u00e1","\u00e0","\u1ea3","\u00e3","\u1ea1"},          /* a á à ả ã ạ */
    {"\u00e2","\u1ea5","\u1ea7","\u1ea9","\u1eab","\u1ead"},     /* â ấ ầ ẩ ẫ ậ */
    {"\u0103","\u1eaf","\u1eb1","\u1eb3","\u1eb5","\u1eb7"},     /* ă ắ ằ ẳ ẵ ặ */
};
/* e, ê (e1) */
static const char *E_[3][6] = {
    {"e","\u00e9","\u00e8","\u1ebb","\u1ebd","\u1eb9"},          /* e é è ẻ ẽ ẹ */
    {"\u00ea","\u1ebf","\u1ec1","\u1ec3","\u1ec5","\u1ec7"},     /* ê ế ề ể ễ ệ */
    {"e","\u00e9","\u00e8","\u1ebb","\u1ebd","\u1eb9"},          /* (no breve) */
};
/* i */
static const char *I_[3][6] = {
    {"i","\u00ed","\u00ec","\u1ec9","\u0129","\u1ecb"},          /* i í ì ỉ ĩ ị */
    {"i","\u00ed","\u00ec","\u1ec9","\u0129","\u1ecb"},
    {"i","\u00ed","\u00ec","\u1ec9","\u0129","\u1ecb"},
};
/* o, ô (o1), ơ (o2) */
static const char *O_[3][6] = {
    {"o","\u00f3","\u00f2","\u1ecf","\u00f5","\u1ecd"},          /* o ó ò ỏ õ ọ */
    {"\u00f4","\u1ed1","\u1ed3","\u1ed5","\u1ed7","\u1ed9"},     /* ô ố ồ ổ ỗ ộ */
    {"\u01a1","\u1edb","\u1edd","\u1edf","\u1ee1","\u1ee3"},     /* ơ ớ ờ ở ỡ ợ */
};
/* u, ư (u2) */
static const char *U_[3][6] = {
    {"u","\u00fa","\u00f9","\u1ee7","\u0169","\u1ee5"},          /* u ú ù ủ ũ ụ */
    {"u","\u00fa","\u00f9","\u1ee7","\u0169","\u1ee5"},
    {"\u01b0","\u1ee9","\u1eeb","\u1eed","\u1eef","\u1ef1"},     /* ư ứ ừ ử ữ ự */
};
/* y */
static const char *Y_[3][6] = {
    {"y","\u00fd","\u1ef3","\u1ef7","\u1ef9","\u1ef5"},          /* y ý ỳ ỷ ỹ ỵ */
    {"y","\u00fd","\u1ef3","\u1ef7","\u1ef9","\u1ef5"},
    {"y","\u00fd","\u1ef3","\u1ef7","\u1ef9","\u1ef5"},
};

/* Uppercase precomposed tables, same [variant][tone] layout. */
/* A Â Ă */
static const char *AU_[3][6] = {
    {"A","\u00c1","\u00c0","\u1ea2","\u00c3","\u1ea0"},
    {"\u00c2","\u1ea4","\u1ea6","\u1ea8","\u1eaa","\u1eac"},
    {"\u0102","\u1eae","\u1eb0","\u1eb2","\u1eb4","\u1eb6"},
};
/* E Ê */
static const char *EU_[3][6] = {
    {"E","\u00c9","\u00c8","\u1eba","\u1ebc","\u1eb8"},
    {"\u00ca","\u1ebe","\u1ec0","\u1ec2","\u1ec4","\u1ec6"},
    {"E","\u00c9","\u00c8","\u1eba","\u1ebc","\u1eb8"},
};
/* I */
static const char *IU_[3][6] = {
    {"I","\u00cd","\u00cc","\u1ec8","\u0128","\u1eca"},
    {"I","\u00cd","\u00cc","\u1ec8","\u0128","\u1eca"},
    {"I","\u00cd","\u00cc","\u1ec8","\u0128","\u1eca"},
};
/* O Ô Ơ */
static const char *OU_[3][6] = {
    {"O","\u00d3","\u00d2","\u1ece","\u00d5","\u1ecc"},
    {"\u00d4","\u1ed0","\u1ed2","\u1ed4","\u1ed6","\u1ed8"},
    {"\u01a0","\u1eda","\u1edc","\u1ede","\u1ee0","\u1ee2"},
};
/* U Ư */
static const char *UU_[3][6] = {
    {"U","\u00da","\u00d9","\u1ee6","\u0168","\u1ee4"},
    {"U","\u00da","\u00d9","\u1ee6","\u0168","\u1ee4"},
    {"\u01af","\u1ee8","\u1eea","\u1eec","\u1eee","\u1ef0"},
};
/* Y */
static const char *YU_[3][6] = {
    {"Y","\u00dd","\u1ef2","\u1ef6","\u1ef8","\u1ef4"},
    {"Y","\u00dd","\u1ef2","\u1ef6","\u1ef8","\u1ef4"},
    {"Y","\u00dd","\u1ef2","\u1ef6","\u1ef8","\u1ef4"},
};

static const char *vowel_utf8(char base, int variant, int tone, int upper) {
    if (variant < 0 || variant > 2) variant = 0;
    if (tone < 0 || tone > 5) tone = 0;
    if (upper) {
        switch (base) {
            case 'a': return AU_[variant][tone];
            case 'e': return EU_[variant][tone];
            case 'i': return IU_[variant][tone];
            case 'o': return OU_[variant][tone];
            case 'u': return UU_[variant][tone];
            case 'y': return YU_[variant][tone];
            default:  return NULL;
        }
    }
    switch (base) {
        case 'a': return A_[variant][tone];
        case 'e': return E_[variant][tone];
        case 'i': return I_[variant][tone];
        case 'o': return O_[variant][tone];
        case 'u': return U_[variant][tone];
        case 'y': return Y_[variant][tone];
        default:  return NULL;
    }
}

static int is_vowel(char c) {
    c = (char)tolower((unsigned char)c);
    return c=='a'||c=='e'||c=='i'||c=='o'||c=='u'||c=='y';
}

/* Uppercase a UTF-8 Vietnamese string in place is complex; instead we track
 * caps per output char at emit time via a simple ASCII fallback. */

/*
 * Word-level Telex conversion.
 * Strategy: walk input, maintain an output list of "letters" where vowels
 * carry (variant,tone). Modifier keys mutate the last matching vowel/char.
 */

typedef struct {
    char c;        /* ASCII base letter, lowercase */
    int  is_vowel;
    int  variant;  /* for vowels */
    int  tone;     /* for vowels */
    int  is_dstroke; /* d -> đ */
    int  upper;
} Letter;

static int emit_letters(Letter *ls, int n, char *out, int max) {
    int p = 0;
    for (int i = 0; i < n && p < max - 4; i++) {
        const char *s;
        char tmp[2];
        if (ls[i].is_dstroke) {
            s = ls[i].upper ? "\u0110" : "\u0111"; /* Đ / đ */
        } else if (ls[i].is_vowel) {
            s = vowel_utf8(ls[i].c, ls[i].variant, ls[i].tone, ls[i].upper);
            if (!s) { tmp[0] = ls[i].upper ? (char)toupper((unsigned char)ls[i].c) : ls[i].c; tmp[1] = 0; s = tmp; }
        } else {
            tmp[0] = ls[i].upper ? (char)toupper((unsigned char)ls[i].c) : ls[i].c;
            tmp[1] = 0;
            s = tmp;
        }
        int L = (int)strlen(s);
        if (p + L >= max - 1) break;
        memcpy(out + p, s, L);
        p += L;
    }
    out[p] = 0;
    return p;
}

/* Find index of last vowel (for applying marks like ^, breve, horn). */
static int last_vowel_index(Letter *ls, int n) {
    int idx = -1;
    for (int i = 0; i < n; i++) if (ls[i].is_vowel) idx = i;
    return idx;
}

/*
 * Choose which vowel in the syllable carries the TONE.
 * Simplified Vietnamese rule:
 *  - find the rightmost contiguous vowel cluster
 *  - if any vowel in it has a variant (^, breve, horn), tone goes there
 *  - else for a 2-vowel cluster not ending the word (has trailing consonant),
 *    tone goes on the 2nd vowel; otherwise on the 1st (open diphthong).
 */
static int tone_vowel_index(Letter *ls, int n) {
    int end = -1;
    for (int i = n - 1; i >= 0; i--) { if (ls[i].is_vowel) { end = i; break; } }
    if (end < 0) return -1;
    int start = end;
    while (start - 1 >= 0 && ls[start - 1].is_vowel) start--;

    for (int i = start; i <= end; i++)
        if (ls[i].variant != 0) return i;

    int count = end - start + 1;
    if (count == 1) return start;

    int has_trailing_consonant = (end < n - 1);  /* consonant after cluster */
    if (has_trailing_consonant) return end;       /* closed: 2nd vowel */
    return start;                                  /* open diphthong: 1st vowel */
}

static int tone_from_telex(char c) {
    switch (tolower((unsigned char)c)) {
        case 's': return T_SAC;
        case 'f': return T_HUYEN;
        case 'r': return T_HOI;
        case 'x': return T_NGA;
        case 'j': return T_NANG;
        default:  return -1;
    }
}

static int convert_telex(const char *in, char *out, int max) {
    Letter ls[64];
    int n = 0;
    for (const char *p = in; *p && n < 63; p++) {
        char c = *p;
        char lc = (char)tolower((unsigned char)c);
        int upper = isupper((unsigned char)c) ? 1 : 0;

        /* dd -> đ */
        if (lc == 'd' && n > 0 && ls[n-1].c == 'd' && !ls[n-1].is_dstroke
            && !ls[n-1].is_vowel) {
            ls[n-1].is_dstroke = 1;
            continue;
        }

        /* circumflex: aa ee oo (double same vowel) */
        if (is_vowel(lc) && n > 0 && ls[n-1].is_vowel && ls[n-1].c == lc
            && ls[n-1].variant == 0 && (lc=='a'||lc=='e'||lc=='o')) {
            ls[n-1].variant = 1;
            continue;
        }

        /* breve/horn via w */
        if (lc == 'w') {
            int vi = last_vowel_index(ls, n);
            if (vi >= 0) {
                char b = ls[vi].c;
                if (b=='a') { ls[vi].variant = 2; continue; }      /* ă */
                if (b=='o') { ls[vi].variant = 2; continue; }      /* ơ */
                if (b=='u') { ls[vi].variant = 2; continue; }      /* ư */
                if (b=='e') { ls[vi].variant = 1; continue; }      /* (aw fallback) */
            }
            /* standalone w -> could be uw; just drop as literal 'w' */
        }

        /* tone marks */
        int t = tone_from_telex(lc);
        if (t >= 0) {
            int vi = tone_vowel_index(ls, n);
            if (vi >= 0 && ls[vi].tone == T_NONE) {
                ls[vi].tone = t;
                continue;
            }
            /* z removes tone handled below */
        }
        if (lc == 'z') {
            int vi = tone_vowel_index(ls, n);
            if (vi >= 0) { ls[vi].tone = T_NONE; continue; }
        }

        /* normal letter */
        ls[n].c = lc;
        ls[n].is_vowel = is_vowel(lc);
        ls[n].variant = 0;
        ls[n].tone = T_NONE;
        ls[n].is_dstroke = 0;
        ls[n].upper = upper;
        n++;
    }
    return emit_letters(ls, n, out, max);
}

static int vni_tone(char c) {
    switch (c) {
        case '1': return T_SAC;
        case '2': return T_HUYEN;
        case '3': return T_HOI;
        case '4': return T_NGA;
        case '5': return T_NANG;
        default:  return -1;
    }
}

static int convert_vni(const char *in, char *out, int max) {
    Letter ls[64];
    int n = 0;
    for (const char *p = in; *p && n < 63; p++) {
        char c = *p;
        char lc = (char)tolower((unsigned char)c);
        int upper = isupper((unsigned char)c) ? 1 : 0;

        int t = vni_tone(lc);
        if (t >= 0) {
            int vi = tone_vowel_index(ls, n);
            if (vi >= 0) { ls[vi].tone = t; continue; }
        }
        if (lc == '6') { /* circumflex a/e/o */
            int vi = last_vowel_index(ls, n);
            if (vi >= 0 && (ls[vi].c=='a'||ls[vi].c=='e'||ls[vi].c=='o')) {
                ls[vi].variant = 1; continue;
            }
        }
        if (lc == '7') { /* horn o/u */
            int vi = last_vowel_index(ls, n);
            if (vi >= 0 && (ls[vi].c=='o'||ls[vi].c=='u')) { ls[vi].variant = 2; continue; }
        }
        if (lc == '8') { /* breve a */
            int vi = last_vowel_index(ls, n);
            if (vi >= 0 && ls[vi].c=='a') { ls[vi].variant = 2; continue; }
        }
        if (lc == '9') { /* d -> đ */
            for (int i = n-1; i >= 0; i--) if (ls[i].c=='d' && !ls[i].is_vowel) { ls[i].is_dstroke = 1; break; }
            continue;
        }
        if (lc == '0') continue; /* remove tone marker (ignored) */

        ls[n].c = lc;
        ls[n].is_vowel = is_vowel(lc);
        ls[n].variant = 0;
        ls[n].tone = T_NONE;
        ls[n].is_dstroke = 0;
        ls[n].upper = upper;
        n++;
    }
    return emit_letters(ls, n, out, max);
}

/*
 * VIQR conversion.
 *
 * VIQR uses ASCII punctuation as diacritic markers:
 *   ^ circumflex, ( breve, + horn (modifiers)
 *   ' sac, ` huyen, ? hoi, ~ nga, . nang (tones)
 *   dd -> d-stroke
 *
 * Each marker applies to the last vowel in the buffer (if legal).
 * Non-marker characters pass through unchanged.
 */
static int convert_viqr(const char *in, char *out, int max) {
    Letter ls[64];
    int n = 0;
    for (const char *p = in; *p && n < 63; p++) {
        char c = *p;

        /* Modifier characters: apply to last vowel */
        if (c == '^' || c == '(' || c == '+') {
            int vi = last_vowel_index(ls, n);
            if (vi >= 0) {
                char b = ls[vi].c;
                if (c == '^' && (b=='a'||b=='e'||b=='o')) {
                    ls[vi].variant = 1; continue;
                }
                if (c == '(' && b == 'a') {
                    ls[vi].variant = 2; continue;
                }
                if (c == '+' && (b=='o'||b=='u')) {
                    ls[vi].variant = 2; continue;
                }
            }
            /* Illegal combination: treat as literal character */
            ls[n].c = c;
            ls[n].is_vowel = 0;
            ls[n].variant = 0;
            ls[n].tone = T_NONE;
            ls[n].is_dstroke = 0;
            ls[n].upper = 0;
            n++;
            continue;
        }

        /* Tone characters: apply to last vowel */
        if (c == '\'') { int vi = last_vowel_index(ls, n); if (vi >= 0) { ls[vi].tone = T_SAC; continue; } }
        if (c == '`')  { int vi = last_vowel_index(ls, n); if (vi >= 0) { ls[vi].tone = T_HUYEN; continue; } }
        if (c == '?')  { int vi = last_vowel_index(ls, n); if (vi >= 0) { ls[vi].tone = T_HOI; continue; } }
        if (c == '~')  { int vi = last_vowel_index(ls, n); if (vi >= 0) { ls[vi].tone = T_NGA; continue; } }
        if (c == '.')  { int vi = last_vowel_index(ls, n); if (vi >= 0) { ls[vi].tone = T_NANG; continue; } }

        /* dd -> d-stroke */
        char lc = (char)tolower((unsigned char)c);
        if (lc == 'd' && n > 0 && ls[n-1].c == 'd' && !ls[n-1].is_dstroke
            && !ls[n-1].is_vowel) {
            ls[n-1].is_dstroke = 1;
            continue;
        }

        /* Normal letter */
        ls[n].c = lc;
        ls[n].is_vowel = is_vowel(lc);
        ls[n].variant = 0;
        ls[n].tone = T_NONE;
        ls[n].is_dstroke = 0;
        ls[n].upper = isupper((unsigned char)c) ? 1 : 0;
        n++;
    }
    return emit_letters(ls, n, out, max);
}

/* ---- Public API (unchanged signatures) -------------------------------- */

int catkey_convert_word(const char *word, char *output, int max_len, int method) {
    if (!word || !output || max_len < 1) return 0;
    if (method == CATKEY_VNI)  return convert_vni(word, output, max_len);
    if (method == CATKEY_VIQR) return convert_viqr(word, output, max_len);
    return convert_telex(word, output, max_len);
}

int catkey_process_input(const char *sequence, char *output, int max_output_len, int method) {
    return catkey_convert_word(sequence, output, max_output_len, method);
}

#ifdef _WIN32
#include <windows.h>
int catkey_modifier_pressed(int vk_code) {
    return (GetAsyncKeyState(vk_code) & 0x8000) ? 1 : 0;
}
#else
int catkey_modifier_pressed(int vk_code) { (void)vk_code; return 0; }
#endif

#ifdef CATKEY_TEST
#include <stdio.h>
int main(void) {
    const char *tests[] = {"dd","aa","chaof","vieejt","tieengs","ddaa","as","af",
                           "Ee","Aa","Ow","Uwx","DDaay","TIEENGS"};
    char o[MAX_OUTPUT_LENGTH];
    for (int i=0;i<14;i++){ catkey_convert_word(tests[i],o,sizeof o,CATKEY_TEIP); printf("%s -> %s\n",tests[i],o);}    
    return 0;
}
#endif
