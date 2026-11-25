# The project's parameters, written by research-kit (code spec section 2). Code never types a number,
# date or path: it reads them from analysis/params.yml (the pipeline's, approved) or
# analysis/explore/params.yml (quick questions) with param("name"), after source() of this file. The files
# are found from this file's own place (or, if that is unknown, from the project folder above the working
# directory), so a script may run from any folder; a missing analysis/params.yml is an error.
local({
  parse_value <- function(v) {
    v <- trimws(v)
    if (v %in% c("true", "false")) return(v == "true")
    if (startsWith(v, "'")) return(gsub("''", "'", substr(v, 2, nchar(v) - 1), fixed = TRUE))
    if (startsWith(v, "[")) {
      inner <- trimws(substr(v, 2, nchar(v) - 1))
      if (!nzchar(inner)) return(c())
      items <- regmatches(inner, gregexpr("'(?:[^']|'')*'|[^,\\s][^,]*", inner, perl = TRUE))[[1]]
      return(unlist(lapply(items, parse_value)))
    }
    as.numeric(v)
  }
  read <- function(path, required) {
    if (!file.exists(path)) {
      if (required) stop(path, ": analysis/params.yml is missing; run the kit's scaffold.py add-params", call. = FALSE)
      return(list())
    }
    lines <- sub("^\ufeff", "", readLines(path, warn = FALSE, encoding = "UTF-8"))
    entries <- grep("^[a-z][a-z0-9_]*:", lines, value = TRUE)
    out <- lapply(sub("^[^:]*: ?", "", entries), parse_value)
    names(out) <- sub(":.*$", "", entries)
    out
  }
  here <- NULL                                  # the innermost source() call is the one that loads this file
  for (i in rev(seq_len(sys.nframe()))) {
    if (identical(sys.function(i), base::source)) {
      f <- sys.frame(i)
      if (is.character(f$ofile)) here <- if (isTRUE(f$chdir)) basename(f$ofile) else f$ofile
      break
    }
  }
  analysis <- if (!is.null(here)) dirname(normalizePath(here)) else {
    marker <- file.path(".claude", "research.yml")                       # literal: the kit's project marker
    d <- normalizePath(getwd())
    while (!file.exists(file.path(d, marker)) && dirname(d) != d) d <- dirname(d)
    if (!file.exists(file.path(d, marker))) {
      stop("params.R: no kit project (.claude/research.yml) in or above ", getwd(), call. = FALSE)
    }
    file.path(d, "analysis")
  }
  params <- c(read(file.path(analysis, "params.yml"), TRUE),                   # literal: the parameter files
              read(file.path(analysis, "explore", "params.yml"), FALSE))      # literal: the parameter files
  twice <- unique(names(params)[duplicated(names(params))])
  if (length(twice)) {
    stop("parameters defined twice in analysis/params.yml and analysis/explore/params.yml: ",
         paste(twice, collapse = ", "), call. = FALSE)
  }
  assign("param", function(name) {
    if (!name %in% names(params)) {
      stop("no parameter '", name, "' in analysis/params.yml or analysis/explore/params.yml", call. = FALSE)
    }
    params[[name]]
  }, envir = globalenv())
  assign("param_path", function(name) {                 # a path parameter, from the project root, for any folder
    value <- get("param", envir = globalenv())(name)
    if (length(value) != 1 || !is.character(value)) stop("parameter '", name, "' is not one path", call. = FALSE)
    if (grepl("^(/|~|[A-Za-z]:[/\\\\])", value)) return(path.expand(value))   # literal: absolute and home paths
    file.path(dirname(analysis), value)
  }, envir = globalenv())
})
