/* Out-of-line definition of the stub canary sink (see magma_canary.h).
 * Kept in a separate, *uninstrumented* TU so the canary call sites in the lua
 * sources survive -O0 codegen (the call cannot be proven dead). We never read
 * the sink; it only prevents the call from being optimised away. */
#include <stddef.h>

volatile unsigned long magma_canary_sink = 0;

void magma_log(const char *bug, int condition) {
    if (condition) {
        magma_canary_sink ^= (unsigned long)(size_t)bug;
    }
}
