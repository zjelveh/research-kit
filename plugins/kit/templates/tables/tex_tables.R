# The paper's LaTeX tables, written by research-kit's table writer (table writer spec); the project owns this
# file and may edit it. A driver builds the paper's style once and passes it to every function:
#   style <- table_style(param)                        # the table_* settings in analysis/params.yml
#   small <- table_style(param, size = "scriptsize")   # one setting overridden, for one table
# Every number goes through tex_number(), so a negative prints with a real minus and a value that rounds to zero
# without a sign; stars and their legend come from the same thresholds. Base R only, so the paper's replication
# code needs nothing else to run it. In a package, the #' lines are roxygen's titles and export tags.

# The paper's table settings, entries of analysis/params.yml; the style's fields drop the table_ prefix.
.tex_tables_settings <- c(
  "table_star_thresholds", "table_star_markers", "table_decimals", "table_thousands", "table_se_brackets",
  "table_interval_brackets", "table_interval_sep", "table_p_decimals", "table_p_floor", "table_p_leading_zero",
  "table_missing", "table_size", "table_placement", "table_caption_period", "table_notes_lead",
  "table_notes_size", "table_notes_width", "table_notes_skip", "table_tabcolsep", "table_arraystretch")
.tex_tables_markers <- c("*", "**", "***", "\\dagger", "\\ddagger")   # the symbols the paper's table check reads
.tex_tables_max <- 6L  # literal: the widest a number, p-value or threshold is printed
.tex_tables_group_size <- 3L  # literal: digits between thousands separators
.tex_tables_minus <- "$-$"
.tex_tables_words <- c("thousands", "interval_sep", "missing", "size", "placement", "notes_lead", "notes_size",
                       "notes_width", "notes_skip", "tabcolsep", "arraystretch")
.tex_tables_pairs <- c("se_brackets", "interval_brackets")

#' The paper's table style, read through the driver's param(); named arguments override settings by field name.
#' @export
table_style <- function(param, ...) {
  if (missing(param) || !is.function(param)) {
    stop("table_style: pass the driver's param function: table_style(param)", call. = FALSE)
  }
  overrides <- list(...)
  fields <- sub("^table_", "", .tex_tables_settings)
  if (length(overrides) && (is.null(names(overrides)) || !all(nzchar(names(overrides))))) {
    stop("table_style: name each override, as in size = \"scriptsize\"", call. = FALSE)
  }
  unknown <- setdiff(names(overrides), fields)
  if (length(unknown)) {
    stop("table_style: no setting named ", paste(sort(unknown), collapse = ", "), "; the settings are ",
         paste(fields, collapse = ", "), call. = FALSE)
  }
  values <- list()
  for (i in seq_along(fields)) {
    name <- .tex_tables_settings[[i]]
    values[fields[[i]]] <- list(if (fields[[i]] %in% names(overrides)) overrides[[fields[[i]]]] else
      tryCatch(param(name), error = function(e) {
        if (!startsWith(conditionMessage(e), "no parameter")) stop(e)
        stop("no parameter ", name, " in analysis/params.yml: the table writer needs every table_* setting ",
             "(research-kit's scaffold.py add-tables adds missing ones)", call. = FALSE)
      }))
  }
  .tex_tables_checked(values)
}

.tex_tables_checked <- function(v) {
  bad <- function(field, why) stop("table_style: table_", field, ": ", why, call. = FALSE)
  thresholds <- if (is.null(v$star_thresholds)) numeric() else v$star_thresholds
  markers <- if (is.null(v$star_markers)) character() else v$star_markers
  if (length(thresholds) != length(markers)) {
    bad("star_markers", paste(length(markers), "markers for", length(thresholds), "thresholds"))
  }
  if (length(thresholds)) {
    if (!is.numeric(thresholds) || anyNA(thresholds) || any(thresholds <= 0 | thresholds >= 1)) {
      bad("star_thresholds", "every threshold is a number between 0 and 1")
    }
    for (t in thresholds) {
      if (is.null(.tex_tables_exact(t))) {
        bad("star_thresholds", paste(t, "doesn't print exactly with", .tex_tables_max, "decimals or fewer"))
      }
    }
    if (anyDuplicated(thresholds)) bad("star_thresholds", "a threshold is given twice")
    if (!is.character(markers) || !all(markers %in% .tex_tables_markers)) {
      bad("star_markers", paste("every marker is one of", paste(.tex_tables_markers, collapse = ", ")))
    }
    if (anyDuplicated(markers)) bad("star_markers", "a marker is given twice")
  }
  v["star_thresholds"] <- list(as.numeric(thresholds))
  v["star_markers"] <- list(as.character(markers))
  for (field in c("decimals", "p_decimals")) v[[field]] <- .tex_tables_decimals(v[[field]], paste0("table_", field))
  floor <- v$p_floor
  if (!is.numeric(floor) || length(floor) != 1L || is.na(floor) || floor <= 0 || floor >= 1 ||
      is.null(.tex_tables_exact(floor))) {
    bad("p_floor", "is not a number between 0 and 1 that prints exactly")
  }
  for (field in c("p_leading_zero", "caption_period")) {
    if (!is.logical(v[[field]]) || length(v[[field]]) != 1L || is.na(v[[field]])) bad(field, "is not true or false")
  }
  for (field in .tex_tables_words) {
    if (!is.character(v[[field]]) || length(v[[field]]) != 1L || is.na(v[[field]])) bad(field, "is not a string")
  }
  for (field in c("notes_width", "notes_skip")) {
    if (!nzchar(trimws(v[[field]]))) bad(field, "is empty; it is a LaTeX length, such as '\\linewidth' or '6pt'")
  }
  for (field in .tex_tables_pairs) {
    if (!is.character(v[[field]]) || length(v[[field]]) != 2L || anyNA(v[[field]])) {
      bad(field, "is not two strings, the opening and the closing one")
    }
  }
  structure(v, class = "tex_tables_style")
}

.tex_tables_decimals <- function(d, what = "decimals") {
  if (!is.numeric(d) || length(d) != 1L || is.na(d) || d != round(d) || d < 0 || d > .tex_tables_max) {
    stop(what, ": ", deparse(d), " is not a whole number from 0 to ", .tex_tables_max, call. = FALSE)
  }
  as.integer(d)
}

.tex_tables_scalar <- function(x, what) {
  if (length(x) != 1L || is.list(x)) {
    stop(what, ": the table writer takes one value at a time, not ", length(x), call. = FALSE)
  }
}

.tex_tables_probability <- function(p) {
  v <- .tex_tables_number(p, "p")
  if (v < 0 || v > 1) stop("p: ", v, " is not a p-value (between 0 and 1)", call. = FALSE)
  v
}

.tex_tables_number <- function(x, what) {
  if (!is.numeric(x)) stop(what, ": ", deparse(x), " is not a number", call. = FALSE)
  if (is.infinite(x)) stop(what, ": an infinite value has no place in a table", call. = FALSE)
  as.numeric(x)
}

.tex_tables_fixed <- function(v, d) sprintf("%.*f", as.integer(d), v)

.tex_tables_zero <- function(text) !grepl("[1-9]", text)

.tex_tables_exact <- function(t) {
  for (d in 2:.tex_tables_max) {
    s <- .tex_tables_fixed(t, d)
    if (as.numeric(s) == t) return(s)
  }
  NULL
}

.tex_tables_group <- function(digits, sep) {
  n <- nchar(digits)
  if (!nzchar(sep) || n <= .tex_tables_group_size) return(digits)
  head <- n %% .tex_tables_group_size
  if (head == 0L) head <- .tex_tables_group_size
  starts <- c(1L, seq.int(head + 1L, n, by = .tex_tables_group_size))
  ends <- c(head, starts[-1L] + .tex_tables_group_size - 1L)
  paste(substring(digits, starts, ends), collapse = sep)
}

.tex_tables_signed <- function(v, d, style, plus = FALSE, prefix = "", suffix = "") {
  body <- .tex_tables_fixed(abs(v), d)
  sign <- if (.tex_tables_zero(body)) "" else if (v < 0) .tex_tables_minus else if (plus) "+" else ""
  parts <- strsplit(body, ".", fixed = TRUE)[[1L]]
  frac <- if (length(parts) > 1L) paste0(".", parts[[2L]]) else ""
  paste0(sign, prefix, .tex_tables_group(parts[[1L]], style$thousands), frac, suffix)
}

.tex_tables_lead <- function(text, style) {
  if (!style$p_leading_zero && startsWith(text, "0.")) substring(text, 2L) else text
}

#' One number for a table cell: a real minus, no sign on a value that prints as zero, thousands separators.
#' @export
tex_number <- function(x, style, decimals = NULL, plus = FALSE, prefix = "", suffix = "") {
  .tex_tables_scalar(x, "x")
  if (is.na(x)) return(style$missing)
  d <- if (is.null(decimals)) style$decimals else .tex_tables_decimals(decimals)
  .tex_tables_signed(.tex_tables_number(x, "x"), d, style, plus, prefix, suffix)
}

#' The marker of the smallest star threshold p is strictly below, as LaTeX; an empty string for none.
#' @export
star_marker <- function(p, style) {
  .tex_tables_scalar(p, "p")
  if (is.na(p)) return("")
  v <- .tex_tables_probability(p)
  if (!length(style$star_thresholds)) return("")
  below <- which(v < style$star_thresholds)
  if (!length(below)) return("")
  paste0("$^{", style$star_markers[[below[which.min(style$star_thresholds[below])]]], "}$")
}

#' The star legend, from the largest threshold down, as LaTeX for the table notes.
#' @export
star_legend <- function(style) {
  if (!length(style$star_thresholds)) return("")
  o <- order(style$star_thresholds, decreasing = TRUE)
  shown <- vapply(style$star_thresholds[o], function(t) .tex_tables_lead(.tex_tables_exact(t), style), "")
  paste0(paste0("$^{", style$star_markers[o], "}p<", shown, "$", collapse = ", "), ".")
}

#' A p-value, never printed as zero or on the other side of a star threshold; below the floor, less than the floor.
#' @export
p_cell <- function(p, style) {
  .tex_tables_scalar(p, "p")
  if (is.na(p)) return(style$missing)
  v <- .tex_tables_probability(p)
  if (v < style$p_floor) return(paste0("$<$", .tex_tables_lead(.tex_tables_exact(style$p_floor), style)))
  d <- style$p_decimals
  while (d < .tex_tables_max && (.tex_tables_zero(.tex_tables_fixed(v, d)) || .tex_tables_crosses(v, d, style))) {
    d <- d + 1L
  }
  .tex_tables_lead(.tex_tables_fixed(v, d), style)
}

.tex_tables_crosses <- function(v, d, style) {
  shown <- as.numeric(.tex_tables_fixed(v, d))
  any((shown < style$star_thresholds) != (v < style$star_thresholds))
}

#' A standard error inside the paper's brackets.
#' @export
se_cell <- function(se, style, decimals = NULL) {
  .tex_tables_scalar(se, "se")
  if (is.na(se)) return(style$missing)
  paste0(style$se_brackets[[1L]], tex_number(se, style, decimals), style$se_brackets[[2L]])
}

#' An interval; a bound that prints as zero but isn't gets more decimals, so its sign shows.
#' @export
interval_cell <- function(lo, hi, style, decimals = NULL) {
  .tex_tables_scalar(lo, "lo")
  .tex_tables_scalar(hi, "hi")
  if (is.na(lo) || is.na(hi)) return(style$missing)
  d <- if (is.null(decimals)) style$decimals else .tex_tables_decimals(decimals)
  bound <- function(x) {
    w <- d
    while (x != 0 && .tex_tables_zero(.tex_tables_fixed(x, w)) && w < .tex_tables_max) w <- w + 1L
    text <- .tex_tables_signed(x, w, style)
    if (x < 0 && .tex_tables_zero(text)) paste0(.tex_tables_minus, text) else text
  }
  paste0(style$interval_brackets[[1L]],
         paste(bound(.tex_tables_number(lo, "lo")), bound(.tex_tables_number(hi, "hi")), sep = style$interval_sep),
         style$interval_brackets[[2L]])
}

#' Cells joined into one table row, with the row end.
#' @export
table_row <- function(cells) {
  if (!is.character(cells)) stop("table_row: every cell is a string (format numbers with tex_number first)",
                                 call. = FALSE)
  paste0(paste(cells, collapse = " & "), " \\\\")
}

#' A header row whose labels span groups of data columns, and its cmidrule line.
#' @export
header_band <- function(groups, columns, lead = 1L) {
  band <- rep("", lead)
  cmids <- character()
  cursor <- lead + 1L
  for (g in groups) {
    lo <- lead + match(g$first, columns)
    hi <- lead + match(g$last, columns)
    if (is.na(lo) || is.na(hi)) stop("header_band: ", g$first, " or ", g$last, " is not a column", call. = FALSE)
    band <- c(band, rep("", lo - cursor), sprintf("\\multicolumn{%d}{c}{%s}", as.integer(hi - lo + 1L), g$label))
    cmids <- c(cmids, sprintf("\\cmidrule(lr){%d-%d}", as.integer(lo), as.integer(hi)))
    cursor <- hi + 1L
  }
  band <- c(band, rep("", lead + length(columns) - cursor + 1L))
  c(paste0(paste(band, collapse = " & "), " \\\\"), paste(cmids, collapse = " "))
}

#' A booktabs table, with the star legend in its notes whenever a row carries a marker.
#' @export
tex_table <- function(colspec, rows, style, caption = NULL, label = NULL, notes = NULL, landscape = FALSE) {
  if (!is.character(rows)) stop("tex_table: rows are strings", call. = FALSE)
  if (is.null(caption) && (!is.null(label) || landscape)) {
    stop("tex_table: a label or landscape needs a caption; without one the manuscript holds the float",
         call. = FALSE)
  }
  if (!is.null(caption) && style$caption_period && !endsWith(trimws(caption, "right"), ".")) {
    stop("tex_table: the paper's captions end with a period: ", caption, call. = FALSE)
  }
  body <- "\\begingroup"
  if (nzchar(style$size)) body <- c(body, paste0("\\", style$size))
  if (nzchar(style$tabcolsep)) body <- c(body, paste0("\\setlength{\\tabcolsep}{", style$tabcolsep, "}"))
  if (nzchar(style$arraystretch)) body <- c(body, paste0("\\renewcommand{\\arraystretch}{", style$arraystretch, "}"))
  body <- c(body, paste0("\\begin{tabular}{", colspec, "}"), "\\toprule", rows, "\\bottomrule", "\\end{tabular}")
  marked <- any(vapply(style$star_markers, function(m) any(grepl(paste0("$^{", m, "}$"), rows, fixed = TRUE)),
                       logical(1L)))
  parts <- c(if (is.null(notes)) "" else trimws(notes), if (marked) star_legend(style) else "")
  text <- paste(parts[nzchar(parts)], collapse = " ")
  if (nzchar(text)) {
    size <- if (nzchar(style$notes_size)) paste0("\\", style$notes_size) else ""
    lead <- c(style$notes_lead, text)
    body <- c(body, paste0("\\par\\vspace{", style$notes_skip, "}"),
              paste0("\\begin{minipage}{", style$notes_width, "}", size),
              paste(lead[nzchar(lead)], collapse = " "), "\\end{minipage}")
  }
  body <- c(body, "\\endgroup")
  if (is.null(caption)) return(paste0(paste(body, collapse = "\n"), "\n"))
  place <- if (nzchar(style$placement)) paste0("[", style$placement, "]") else ""
  out <- c(paste0("\\begin{table}", place), "\\centering", paste0("\\caption{", caption, "}"))
  if (!is.null(label)) out <- c(out, paste0("\\label{", label, "}"))
  out <- c(out, body, "\\end{table}")
  if (landscape) out <- c("\\begin{landscape}", out, "\\end{landscape}")
  paste0(paste(out, collapse = "\n"), "\n")
}

#' Write a table file (UTF-8, LF line endings), creating its folder; its first line names the script that wrote it.
#' @export
write_tex <- function(text, path, made_by = NULL) {
  if (!is.character(text) || length(text) != 1L) {
    stop("write_tex: text is one string, as tex_table() returns", call. = FALSE)
  }
  who <- if (is.null(made_by)) .tex_tables_running_script() else made_by
  first <- if (nzchar(who)) paste0("% Generated by ", who, "; edit the code that writes it, not this file.") else
    "% Generated; edit the code that writes it, not this file."
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  con <- file(path, open = "wb")
  on.exit(close(con))
  writeBin(charToRaw(enc2utf8(paste0(first, "\n", text))), con)
  invisible(path)
}

.tex_tables_running_script <- function() {
  for (i in rev(seq_len(sys.nframe()))) {           # the innermost source() call is the running script
    if (identical(sys.function(i), base::source)) {
      f <- sys.frame(i)$ofile
      if (is.character(f)) return(basename(f))
    }
  }
  file <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  if (length(file)) basename(sub("^--file=", "", file[[1L]])) else ""
}
