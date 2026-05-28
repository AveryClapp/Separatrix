/* Out-of-line definition of the stub canary sink (see magma_canary.h).
 * Kept in a separate, *uninstrumented* TU so the canary call sites in the lua
 * sources survive -O0 codegen (the call cannot be proven dead).
 *
 * Beyond keeping the call live, the sink now records *which* canary sites fired:
 * a triggering run is what SBFL labels a failure. A canary can sit in a hot
 * loop, so writing a file per trigger would reopen it thousands of times per
 * run; instead we mirror sep_rt.c — collect unique (file,line) pairs in a small
 * in-memory set and dump once in a destructor. Sites are few (<= #canaries), so
 * a bounded array with linear dedup is correct and cheap. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAGMA_MAXTRIG 256

volatile unsigned long magma_canary_sink = 0;   /* keeps the call non-dead */

static const char *g_file[MAGMA_MAXTRIG];
static int         g_line[MAGMA_MAXTRIG];
static size_t      g_ntrig = 0;

void magma_log(const char *file, int line, int condition) {
    if (!condition) return;
    magma_canary_sink ^= (unsigned long)line;
    for (size_t i = 0; i < g_ntrig; i++)                 /* dedup: few sites */
        if (g_line[i] == line && strcmp(g_file[i], file) == 0) return;
    if (g_ntrig < MAGMA_MAXTRIG) {
        g_file[g_ntrig] = file;                          /* __FILE__ literal is stable */
        g_line[g_ntrig] = line;
        g_ntrig++;
    }
}

__attribute__((destructor)) static void magma_dump(void) {
    const char *p = getenv("MAGMA_TRIGGERS");
    if (!p) return;
    FILE *f = fopen(p, "w");                              /* one write per run */
    if (!f) return;
    for (size_t i = 0; i < g_ntrig; i++) fprintf(f, "%s:%d\n", g_file[i], g_line[i]);
    fclose(f);
}
