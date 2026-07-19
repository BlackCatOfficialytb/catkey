/*
 * CatKey - Vietnamese Input Method
 * Configuration implementation
 */

#include "config.h"
#include <stdio.h>
#include <ctype.h>
#include <stdarg.h>

int catkey_log_level = CATKEY_LOG_INFO;
catkey_log_func catkey_log_callback = NULL;

void catkey_log_set_callback(catkey_log_func cb) {
    catkey_log_callback = cb;
}

void catkey_log(int level, const char *format, ...) {
    if (level < catkey_log_level) {
        return;
    }

    const char *level_str[] = { "DEBUG", "INFO", "WARN", "ERROR" };
    const char *prefix = (level >= 0 && level <= 3) ? level_str[level] : "UNKNOWN";

    if (catkey_log_callback) {
        va_list args;
        va_start(args, format);
        catkey_log_callback(level, format, args);
        va_end(args);
        return;
    }

    fprintf(stderr, "[CATKEY][%s] ", prefix);

    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);

    fprintf(stderr, "\n");
}

void catkey_word_init(catkey_word_buffer_t *buf) {
    if (buf) {
        buf->length = 0;
        buf->is_voi = 0;
        buf->buffer[0] = '\0';
    }
}

void catkey_word_add(catkey_word_buffer_t *buf, char ch, int vomode) {
    if (!buf || buf->length >= CATKEY_INPUT_BUFFER_SIZE - 1) {
        return;
    }

    buf->buffer[buf->length++] = tolower(ch);

    if (vomode) {
        buf->is_voi = 1;
    }

    buf->buffer[buf->length] = '\0';
}

void catkey_word_reset(catkey_word_buffer_t *buf) {
    if (buf) {
        buf->length = 0;
        buf->is_voi = 0;
        buf->buffer[0] = '\0';
    }
}

const char *catkey_word_get(catkey_word_buffer_t *buf) {
    return (buf) ? buf->buffer : "";
}