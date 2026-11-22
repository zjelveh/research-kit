# research-kit: emit a paper's numbers for numbers_build.py (languages spec §5.1). Base R only.
# make_numbers.R sources this file by its kit path and calls emit_numbers(entries) once.

emit_numbers <- function(entries) {
  fail <- function(...) stop(paste0("emit_numbers: ", ...), call. = FALSE)
  out <- Sys.getenv("KIT_NUMBERS_OUT")
  if (!nzchar(out)) fail("KIT_NUMBERS_OUT is not set: run make_numbers through numbers_build.py")
  if (file.exists(out)) fail(out, " already exists: emit_numbers was called twice in one run")
  one <- function(s) is.character(s) && length(s) == 1 && !is.na(s) && nzchar(s)
  if (!is.list(entries) || is.data.frame(entries))
    fail("entries must be a list of entries, each list(name = , value = , format = , src = )")
  rows <- lapply(seq_along(entries), function(k) {
    x <- entries[[k]]
    if (!is.list(x))
      fail("entry ", k, " must be a list with name, value, format, src (one entry not wrapped in list()?)")
    for (f in c("name", "value", "format", "src"))
      if (is.null(x[[f]])) fail("entry ", k, " lacks '", f, "'")
    for (f in c("name", "format", "src"))
      if (!one(x[[f]])) fail("entry ", k, ": ", f, " must be a single non-empty string")
    v <- x$value
    if (inherits(v, "integer64"))  # sprintf reads its raw bits as a double, so 5 prints as "0"
      fail("value for ", x$name, " is a bit64 integer64: convert with as.numeric() first")
    ok <- (is.numeric(v) && length(v) == 1 && is.finite(v)) ||
          (is.character(v) && length(v) == 1 && !is.na(v))
    if (!ok) fail("value for ", x$name, " must be a single finite number or a single non-NA string")
    value <- tryCatch(
      withCallingHandlers(sprintf(x$format, v),
                          warning = function(w) stop(conditionMessage(w), call. = FALSE)),
      error = function(e) fail("format '", x$format, "' for ", x$name, " failed: ", conditionMessage(e)))
    list(name = x$name, value = value, src = x$src)
  })
  q <- function(s) paste0('"', gsub('"', '""', s, fixed = TRUE, useBytes = TRUE), '"')
  lines <- c("name,value,src", vapply(rows, function(r)
    paste(q(r[["name"]]), q(r[["value"]]), q(r[["src"]]), sep = ","), ""))
  tmp <- paste0(out, ".tmp")
  con <- file(tmp, open = "wb")
  tryCatch(writeLines(lines, con, useBytes = TRUE), finally = close(con))
  if (!file.rename(tmp, out)) fail("could not rename ", tmp, " to ", out)
  invisible(NULL)
}
