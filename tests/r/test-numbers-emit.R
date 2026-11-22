library(testthat)
source(normalizePath(file.path("..", "..", "plugins", "kit", "scripts", "numbers_emit.R")))

entry <- function(...) modifyList(list(name = "coverageMain", value = 0.9412, format = "%.2f",
                                       src = "analysis/s.csv"), list(...))

emit_to <- function(entries) {
  out <- tempfile(fileext = ".csv")
  Sys.setenv(KIT_NUMBERS_OUT = out)
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  emit_numbers(entries)
  read.csv(out, colClasses = "character")
}

test_that("writes formatted rows, commas and quotes intact", {
  df <- emit_to(list(entry(), entry(name = "labelText", value = 'a, "b"', format = "%s")))
  expect_equal(names(df), c("name", "value", "src"))
  expect_equal(df$value, c("0.94", 'a, "b"'))
})

test_that("an empty list writes a header-only file", {
  df <- emit_to(list())
  expect_equal(nrow(df), 0)
  expect_equal(names(df), c("name", "value", "src"))
})

test_that("unset KIT_NUMBERS_OUT is refused", {
  Sys.unsetenv("KIT_NUMBERS_OUT")
  expect_error(emit_numbers(list(entry())), "numbers_build.py")
})

test_that("a second call is refused", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  emit_numbers(list())
  expect_error(emit_numbers(list()), "called twice")
})

test_that("missing fields and bad values are refused", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  e <- entry(); e$src <- NULL
  expect_error(emit_numbers(list(e)), "lacks")
  for (v in list(NA_real_, NaN, Inf, c(1, 2), NA_character_))
    expect_error(emit_numbers(list(entry(value = v))), "single finite")
})

test_that("logical and factor values are refused", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  expect_error(emit_numbers(list(entry(value = TRUE))), "single finite")
  expect_error(emit_numbers(list(entry(value = factor("a")))), "single finite")
})

test_that("bit64 integer64 values are refused, not written as 0", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  v <- structure(5, class = "integer64")
  expect_error(emit_numbers(list(entry(value = v, format = "%.0f"))), "coverageMain.*as.numeric")
})

test_that("bad name, format and src are refused", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  expect_error(emit_numbers(list(entry(name = c("a", "b")))), "single non-empty string")
  expect_error(emit_numbers(list(entry(format = NA_character_))), "single non-empty string")
  expect_error(emit_numbers(list(entry(format = "abc"))), "failed")
  expect_error(emit_numbers(list(entry(format = "%%"))), "failed")
})

test_that("%d needs a whole number and names the entry", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  expect_error(emit_numbers(list(entry(value = 0.94, format = "%d"))), "coverageMain")
  df <- emit_to(list(entry(value = 3, format = "%d")))
  expect_equal(df$value, "3")
})

test_that("an unwrapped entry is refused", {
  Sys.setenv(KIT_NUMBERS_OUT = tempfile(fileext = ".csv"))
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"))
  expect_error(emit_numbers(entry()), "not wrapped")
})

test_that("non-ASCII values are written as UTF-8 bytes under a C locale", {
  out <- tempfile(fileext = ".csv")
  Sys.setenv(KIT_NUMBERS_OUT = out)
  on.exit(Sys.unsetenv("KIT_NUMBERS_OUT"), add = TRUE)
  old <- Sys.getlocale("LC_CTYPE")
  Sys.setlocale("LC_CTYPE", "C")
  on.exit(Sys.setlocale("LC_CTYPE", old), add = TRUE)
  v <- enc2utf8("caf\u00e9, \"x\"")
  emit_numbers(list(entry(name = "labelText", value = v, format = "%s")))
  Sys.setlocale("LC_CTYPE", old)
  line <- readLines(out, encoding = "UTF-8")[2]
  expect_equal(line, enc2utf8("\"labelText\",\"caf\u00e9, \"\"x\"\"\",\"analysis/s.csv\""))
})
