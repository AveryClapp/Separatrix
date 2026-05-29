/* Separatrix file-mode harness for libpng (Phase-4 eval target).
 *
 * Decodes the PNG named by argv[1] and prints a deterministic value-space digest
 * to stdout:
 *
 *     S<status> <WxH> <fnv64(decoded-raster)>
 *
 * The status + dimensions + raster hash is the program's observable output: a bug
 * that corrupts a decoded pixel changes the FNV-64, and a bug that crashes or
 * aborts the decode changes the status — exactly the output-manifesting property
 * lua lacked. The campaign's value-space predictor measures distance over this
 * digest; the trajectory predictor measures divergence over the instrumented
 * execution trace.
 *
 * Modeled on Magma's libpng read fuzzer (contrib/oss-fuzz/libpng_read_fuzzer.cc):
 * the SAME decode flow and browser transforms, made PERMISSIVE so a mutated byte
 * propagates into the decoder instead of aborting at the first integrity check —
 *   png_set_crc_action(PNG_CRC_QUIET_USE, PNG_CRC_QUIET_USE)
 * (use a chunk even if its CRC is wrong, quietly). Input is read from a file path
 * (not argv bytes) so arbitrary/NUL-containing perturbations are safe.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "png.h"

#define PNG_HEADER_SIZE 8
#define FNV64_OFFSET 14695981039346656037ULL
#define FNV64_PRIME  1099511628211ULL

/* memory reader over the file buffer (past the 8-byte signature) */
typedef struct { const unsigned char *data; size_t left; } buf_state;

static void user_read_data(png_structp png_ptr, png_bytep out, size_t length) {
    buf_state *bs = (buf_state *)png_get_io_ptr(png_ptr);
    if (length > bs->left)
        png_error(png_ptr, "read past end");   /* longjmp back to setjmp */
    memcpy(out, bs->data, length);
    bs->left -= length;
    bs->data += length;
}

/* match the fuzzer's OOM guard so a perturbed size field can't drive a giant
 * allocation that would manifest as an allocator difference rather than a bug. */
static void *limited_malloc(png_structp p, png_alloc_size_t size) {
    (void)p;
    if (size > 8000000) return NULL;
    return malloc((size_t)size);
}
static void default_free(png_structp p, png_voidp ptr) { (void)p; free(ptr); }

static unsigned long long g_hash = FNV64_OFFSET;
static void fnv64(const unsigned char *p, size_t n) {
    for (size_t i = 0; i < n; i++) {
        g_hash ^= p[i];
        g_hash *= FNV64_PRIME;
    }
}

static unsigned char *read_file(const char *path, size_t *out_n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 0) { fclose(f); return NULL; }
    unsigned char *buf = (unsigned char *)malloc((size_t)sz + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t n = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    *out_n = n;
    return buf;
}

/* every exit path prints exactly one digest line, so the output is deterministic
 * regardless of where the decode stopped. */
static void emit(int status, png_uint_32 w, png_uint_32 h) {
    printf("S%d %ux%u %016llx\n", status, (unsigned)w, (unsigned)h, g_hash);
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <png-file>\n", argv[0]); return 2; }
    size_t n = 0;
    unsigned char *data = read_file(argv[1], &n);
    if (!data) { emit(-1, 0, 0); return 0; }                 /* read error */
    if (n < PNG_HEADER_SIZE || png_sig_cmp(data, 0, PNG_HEADER_SIZE)) {
        emit(-2, 0, 0); free(data); return 0;                /* not a PNG */
    }

    png_structp png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    if (!png_ptr) { emit(-3, 0, 0); free(data); return 0; }
    png_infop info_ptr = png_create_info_struct(png_ptr);
    if (!info_ptr) {
        png_destroy_read_struct(&png_ptr, NULL, NULL);
        emit(-3, 0, 0); free(data); return 0;
    }

    png_uint_32 width = 0, height = 0;
    png_bytep row = NULL;

    /* any libpng error longjmps here: emit whatever was decoded so far. The
     * status is 1 (decode error) and the partial raster hash still discriminates
     * buggy from fixed when a bug changes how far/whether the decode proceeds. */
    if (setjmp(png_jmpbuf(png_ptr))) {
        if (row) png_free(png_ptr, row);
        png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
        emit(1, width, height); free(data); return 0;
    }

    png_set_mem_fn(png_ptr, NULL, limited_malloc, default_free);
    /* PERMISSIVE: use chunks even with bad CRC so a mutated byte reaches the
     * decoder instead of aborting at the first integrity check. */
    png_set_crc_action(png_ptr, PNG_CRC_QUIET_USE, PNG_CRC_QUIET_USE);
#ifdef PNG_IGNORE_ADLER32
    png_set_option(png_ptr, PNG_IGNORE_ADLER32, PNG_OPTION_ON);
#endif

    buf_state bs = { data + PNG_HEADER_SIZE, n - PNG_HEADER_SIZE };
    png_set_read_fn(png_ptr, &bs, user_read_data);
    png_set_sig_bytes(png_ptr, PNG_HEADER_SIZE);

    png_read_info(png_ptr, info_ptr);

    int bit_depth, color_type, interlace_type, compression_type, filter_type;
    if (!png_get_IHDR(png_ptr, info_ptr, &width, &height, &bit_depth,
                      &color_type, &interlace_type, &compression_type, &filter_type)) {
        png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
        emit(2, 0, 0); free(data); return 0;                 /* no IHDR */
    }
    if (width && height > 100000000u / width) {              /* too slow / huge */
        png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
        emit(3, width, height); free(data); return 0;
    }

    /* the same browser transforms the Magma fuzzer applies (normalize to 8-bit
     * RGBA-ish), so the decoded raster — and any bug perturbing it — is exercised. */
    png_set_gray_to_rgb(png_ptr);
    png_set_expand(png_ptr);
    png_set_packing(png_ptr);
    png_set_scale_16(png_ptr);
    png_set_tRNS_to_alpha(png_ptr);

    int passes = png_set_interlace_handling(png_ptr);
    png_read_update_info(png_ptr, info_ptr);

    row = (png_bytep)png_malloc(png_ptr, png_get_rowbytes(png_ptr, info_ptr));
    for (int pass = 0; pass < passes; pass++) {
        for (png_uint_32 y = 0; y < height; y++) {
            png_read_row(png_ptr, row, NULL);
            fnv64(row, png_get_rowbytes(png_ptr, info_ptr));
        }
    }

    png_read_end(png_ptr, info_ptr);
    png_free(png_ptr, row); row = NULL;
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    emit(0, width, height);                                  /* full decode */
    free(data);
    return 0;
}
