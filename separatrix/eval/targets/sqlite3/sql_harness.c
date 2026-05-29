/* Separatrix file-mode harness for sqlite3 (Phase-4 eval target).
 *
 * Reads a SQL script from the file named by argv[1], runs it against a fresh
 * in-memory database, and prints a deterministic value-space digest to stdout:
 *
 *     S<rc> rows=<N> <fnv64(result-rows)>
 *
 * The result-row hash + statement return code is the program's observable output.
 * sqlite3's Magma bugs are predominantly LOGIC bugs (wrong query result / planner
 * mistakes), so a triggered bug changes the result rows -> the differential oracle
 * (buggy digest != fixed digest) fires WITHOUT a sanitizer, and the bug class is a
 * control-flow effect that a trajectory-divergence signal can localize. This is
 * the intended first competitiveness target (vs the memory-safety targets, where
 * the bug effect is data corruption invisible to control flow).
 *
 * Input via a file path keeps arbitrary inputs safe. Built deterministically; a
 * SELECT's row order is stable for a given build + data, so any buggy-vs-fixed
 * difference is a genuine behavioral divergence.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sqlite3.h"

#define FNV64_OFFSET 14695981039346656037ULL
#define FNV64_PRIME  1099511628211ULL

static unsigned long long g_hash = FNV64_OFFSET;
static long g_rows = 0;

static void fnv_str(const char *s) {
    if (!s) { g_hash ^= 0xA5; g_hash *= FNV64_PRIME; return; }   /* NULL marker */
    for (; *s; s++) { g_hash ^= (unsigned char)*s; g_hash *= FNV64_PRIME; }
    g_hash ^= 0x1F; g_hash *= FNV64_PRIME;                       /* field separator */
}

/* one result row: fold column count + each column value into the digest, in the
 * order sqlite returns them (deterministic for a given build + data). */
static int row_cb(void *unused, int ncol, char **vals, char **cols) {
    (void)unused; (void)cols;
    g_rows++;
    g_hash ^= (unsigned)ncol; g_hash *= FNV64_PRIME;
    for (int i = 0; i < ncol; i++) fnv_str(vals[i]);
    g_hash ^= 0x0D; g_hash *= FNV64_PRIME;                       /* row separator */
    return 0;
}

static char *read_file(const char *path, size_t *out_n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 0) { fclose(f); return NULL; }
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t n = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    buf[n] = '\0';
    *out_n = n;
    return buf;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <sql-file>\n", argv[0]); return 2; }
    size_t n = 0;
    char *sql = read_file(argv[1], &n);
    if (!sql) { printf("S-1 rows=0 %016llx\n", g_hash); return 0; }

    sqlite3 *db = NULL;
    int rc = sqlite3_open(":memory:", &db);
    if (rc != SQLITE_OK) {
        printf("S%d rows=0 %016llx\n", rc, g_hash);
        sqlite3_close(db); free(sql); return 0;
    }
    char *err = NULL;
    rc = sqlite3_exec(db, sql, row_cb, NULL, &err);
    /* rc + accumulated row hash IS the observable output; err text is not folded
     * in (its wording varies across builds and is not the bug signal). */
    printf("S%d rows=%ld %016llx\n", rc, g_rows, g_hash);
    if (err) sqlite3_free(err);
    sqlite3_close(db);
    free(sql);
    return 0;
}
