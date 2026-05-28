/* Stub Magma canary macros for the native Separatrix port.
 *
 * Magma's real canaries call into a logging runtime that records bug
 * reached/triggered counts. We don't need firings — only the *source location*
 * of each canary, which is the ground-truth bug site. So MAGMA_LOG compiles to a
 * real (non-eliminable) call at the canary line, giving that line a behavioral-
 * graph node we can label as a bug region. Compile patched sources with
 * -DMAGMA_ENABLE_CANARIES and WITHOUT MAGMA_ENABLE_FIXES (buggy branch live).
 */
#ifndef SEP_MAGMA_CANARY_H
#define SEP_MAGMA_CANARY_H
#include <limits.h>   /* INT_MAX, used by some canary conditions */

void magma_log(const char *bug, int condition);
static inline int magma_and(int a, int b) { return a && b; }
static inline int magma_or(int a, int b) { return a || b; }

#define MAGMA_LOG(b, c)   do { magma_log((b), (int)(c)); } while (0)
#define MAGMA_LOG_V(b, c) (magma_log((b), (int)(c)))
#define MAGMA_AND(a, b)   magma_and((a), (b))
#define MAGMA_OR(a, b)    magma_or((a), (b))

#endif
