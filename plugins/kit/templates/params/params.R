# The project's parameters, written by research-kit (code spec section 2). Code never types a number,
# date or path: it reads them from analysis/params.yml (the pipeline's, approved) or
# analysis/explore/params.yml (quick questions) with param("name"). Run scripts from the project root,
# after source("analysis/params.R").
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
  read <- function(path) {
    if (!file.exists(path)) return(list())
    lines <- sub("^\ufeff", "", readLines(path, warn = FALSE, encoding = "UTF-8"))
    entries <- grep("^[a-z][a-z0-9_]*:", lines, value = TRUE)
    out <- lapply(sub("^[^:]*: ?", "", entries), parse_value)
    names(out) <- sub(":.*$", "", entries)
    out
  }
  params <- c(read("analysis/params.yml"), read("analysis/explore/params.yml"))  # literal: the parameter files
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
})
