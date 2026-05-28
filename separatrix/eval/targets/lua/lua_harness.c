/* Separatrix file-mode harness for lua (Phase-4 eval target).
 *
 * Reads a Lua chunk from the file named by argv[1], loads and runs it, then
 * prints a deterministic value-space digest to stdout:
 *
 *     S<load_or_run_status> <result-or-error-message>
 *
 * The status + message is the program's observable output; the campaign's
 * value-space predictor measures distance over this digest, while the trajectory
 * predictor measures divergence over the instrumented execution trace. Input via
 * a file path (not argv bytes) keeps arbitrary/NUL-containing inputs safe.
 */
#include <stdio.h>
#include <stdlib.h>
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

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
    if (argc < 2) { fprintf(stderr, "usage: %s <chunk-file>\n", argv[0]); return 2; }
    size_t n = 0;
    char *buf = read_file(argv[1], &n);
    if (!buf) { printf("S-1 read-error\n"); return 0; }

    lua_State *L = luaL_newstate();
    /* Open only the libraries the eval seeds exercise. Opening *all* stdlibs
     * (luaL_openlibs) adds a ~70k-event constant init prefix that dominates the
     * trace and slows the campaign without adding signal. */
    static const luaL_Reg libs[] = {
        {LUA_GNAME, luaopen_base},
        {LUA_DBLIBNAME, luaopen_debug},
        {LUA_IOLIBNAME, luaopen_io},
        {LUA_STRLIBNAME, luaopen_string},
        {LUA_TABLIBNAME, luaopen_table},
        {NULL, NULL},
    };
    for (const luaL_Reg *lib = libs; lib->func; lib++) {
        luaL_requiref(L, lib->name, lib->func, 1);
        lua_pop(L, 1);
    }

    int st = luaL_loadbuffer(L, buf, n, "chunk");
    if (st == LUA_OK)
        st = lua_pcall(L, 0, 1, 0);

    const char *msg;
    if (st != LUA_OK)
        msg = lua_tostring(L, -1);          /* error message */
    else if (lua_gettop(L) > 0)
        msg = lua_tostring(L, -1);          /* returned value as string */
    else
        msg = "nil";
    printf("S%d %s\n", st, msg ? msg : "?");

    lua_close(L);
    free(buf);
    return 0;
}
