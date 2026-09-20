#pragma once
// Only the small diagnostic surface used by the imported asset bridges.
// Keep arguments visible in failures without pulling desktop log sinks/threads.
#include <cstdio>
#include <string>
extern "C" void port_log(const char*, ...);
namespace spdlog {
inline void value(const char* x) { port_log(" %s", x ? x : "(null)"); }
inline void value(const std::string& x) { value(x.c_str()); }
template<class T> inline void value(T* x) { port_log(" %p", (void*)x); }
template<class T> inline void value(T x) { port_log(" %lld", (long long)x); }
template<class... T> inline void error(const char* fmt, const T&... args) {
    port_log("ERROR %s", fmt); (value(args), ...); port_log("\n");
}
template<class... T> inline void warn(const char* fmt, const T&... args) {
    port_log("WARN %s", fmt); (value(args), ...); port_log("\n");
}
template<class... T> inline void info(const char* fmt, const T&... args) {
    port_log("INFO %s", fmt); (value(args), ...); port_log("\n");
}
template<class... T> inline void debug(const char*, const T&...) {}
}
