/*
 * CatKey - Vietnamese Input Method
 * Shared TEIP/VNI implementation header
 */

#ifndef CATKEY_VIETNAMESE_TEP_H
#define CATKEY_VIETNAMESE_TEP_H

#ifdef __cplusplus
extern "C" {
#endif

#define CATKEY_METHOD_RAW      0
#define CATKEY_METHOD_TEIP     1
#define CATKEY_METHOD_VNI      2
#define CATKEY_METHOD_VIQR     3
#define CATKEY_METHOD_TEIP_VNI 4

#define CATKEY_MAX_KEY_SEQUENCE   10
#define CATKEY_MAX_OUTPUT_LENGTH  32

int catkey_process_input(const char *sequence, char *output, int max_output_len, int method);
int catkey_convert_word(const char *word, char *output, int max_len, int method);
int catkey_modifier_pressed(int vk_code);

#ifdef __cplusplus
}
#endif

#endif