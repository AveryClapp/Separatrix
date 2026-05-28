#include "separatrix/ir/graph.h"

#include <cstdio>

namespace sep {

namespace {

void writeEscaped(std::FILE *f, const std::string &s) {
  std::fputc('"', f);
  for (char c : s) {
    switch (c) {
      case '"':  std::fputs("\\\"", f); break;
      case '\\': std::fputs("\\\\", f); break;
      case '\n': std::fputs("\\n", f);  break;
      case '\t': std::fputs("\\t", f);  break;
      case '\r': std::fputs("\\r", f);  break;
      default:
        if (static_cast<unsigned char>(c) < 0x20)
          std::fprintf(f, "\\u%04x", c);
        else
          std::fputc(c, f);
    }
  }
  std::fputc('"', f);
}

template <typename T>
void writeIntArray(std::FILE *f, const std::vector<T> &v) {
  std::fputc('[', f);
  for (size_t i = 0; i < v.size(); ++i) {
    if (i) std::fputc(',', f);
    std::fprintf(f, "%llu", static_cast<unsigned long long>(v[i]));
  }
  std::fputc(']', f);
}

void writeStrArray(std::FILE *f, const std::vector<std::string> &v) {
  std::fputc('[', f);
  for (size_t i = 0; i < v.size(); ++i) {
    if (i) std::fputc(',', f);
    writeEscaped(f, v[i]);
  }
  std::fputc(']', f);
}

}  // namespace

void BehavioralGraph::writeJson(const std::string &path) const {
  std::FILE *f = std::fopen(path.c_str(), "w");
  if (!f) return;

  std::fputs("{\n  \"module\": ", f);
  writeEscaped(f, module);
  std::fputs(",\n  \"nodes\": [\n", f);
  for (size_t i = 0; i < nodes.size(); ++i) {
    const Node &n = nodes[i];
    std::fputs("    {", f);
    std::fprintf(f, "\"id\": %u, \"function\": ", n.id);
    writeEscaped(f, n.function);
    std::fprintf(f, ", \"block_index\": %u, \"file\": ", n.block_index);
    writeEscaped(f, n.file);
    std::fprintf(f, ", \"line\": %u, \"terminator\": ", n.line);
    writeEscaped(f, n.terminator);
    std::fputs(", \"branch_cond\": ", f);
    writeEscaped(f, n.branch_cond);
    std::fputs(", \"succ\": ", f);
    writeIntArray(f, n.succ);
    std::fputs(", \"calls\": ", f);
    writeStrArray(f, n.call_names);
    std::fputs(i + 1 < nodes.size() ? "},\n" : "}\n", f);
  }
  std::fputs("  ],\n  \"edges\": [\n", f);
  for (size_t i = 0; i < edges.size(); ++i) {
    const Edge &e = edges[i];
    std::fprintf(f, "    {\"from\": %u, \"to\": %u, \"kind\": \"%s\"}",
                 e.from, e.to, e.kind == EdgeKind::Call ? "call" : "cfg");
    std::fputs(i + 1 < edges.size() ? ",\n" : "\n", f);
  }
  std::fputs("  ]\n}\n", f);
  std::fclose(f);
}

}  // namespace sep
