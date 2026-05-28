// Separatrix trace runtime. Compiled into the instrumented target.
//
// Records the ordered sequence of basic-block IDs emitted by
// __sep_trace_block (inserted by `separatrix analyze`) to $SEP_TRACE. IDs are
// the behavioral-graph node IDs, so the trace maps directly onto graph nodes.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define SEP_MAXTRACE 8000000

static uint32_t *g_trace;
static size_t g_n = 0;
static int g_ready = 0;

__attribute__((constructor)) static void sep_init(void) {
  g_trace = (uint32_t *)malloc(sizeof(uint32_t) * SEP_MAXTRACE);
  g_ready = (g_trace != NULL);
}

void __sep_trace_block(uint32_t id) {
  if (g_ready && g_n < SEP_MAXTRACE) g_trace[g_n++] = id;
}

__attribute__((destructor)) static void sep_dump(void) {
  const char *p = getenv("SEP_TRACE");
  if (!p) return;
  FILE *f = fopen(p, "w");
  if (!f) return;
  for (size_t i = 0; i < g_n; i++) fprintf(f, "%u\n", g_trace[i]);
  fclose(f);
}
