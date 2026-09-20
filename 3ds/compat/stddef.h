/* Game-only stddef compatibility. Newlib requests wint_t by
 * defining __need_wint_t; the original N64 shim does not implement that path.
 * Deliberately no include guard: Clang's partial includes are repeatable. */
#include <__stddef_header_macro.h>
#include <__stddef_ptrdiff_t.h>
#include <__stddef_size_t.h>
#include <__stddef_wchar_t.h>
#include <__stddef_null.h>
#undef NULL
#define NULL 0
#include <__stddef_offsetof.h>
#ifdef __need_wint_t
#include <__stddef_wint_t.h>
#undef __need_wint_t
#endif
