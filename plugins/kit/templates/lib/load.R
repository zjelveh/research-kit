# The paper's R library, loaded by research-kit's loader (code spec section 4): every .R file in this folder, in
# name order, except test files (test_*.R, test-*.R) and this file. Library files hold definitions only, so the
# order doesn't matter: R looks up the names in a function's body when the function is called. A script sources
# analysis/params.R first, then this file, each by its path from the script's working folder. This file finds
# its own folder, so a script may run from any folder in the project.
local({
  here <- NULL                                  # the innermost source() call is the one that loads this file
  for (i in rev(seq_len(sys.nframe()))) {
    if (identical(sys.function(i), base::source)) {
      f <- sys.frame(i)
      if (is.character(f$ofile)) here <- if (isTRUE(f$chdir)) basename(f$ofile) else f$ofile
      break
    }
  }
  if (is.null(here)) stop("load.R: source() this file by its path", call. = FALSE)
  here <- normalizePath(here)
  files <- normalizePath(list.files(dirname(here), pattern = "[.][Rr]$", full.names = TRUE))
  files <- sort(files[!grepl("^test[-_]", basename(files)) & files != here], method = "radix")
  for (f in files) source(f)
})
