# Unicode whitespace that text columns must not start or end with
TRIM_CHARS_SQL = (
    "U&'"
    "\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680"
    "\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A"
    "\\2028\\2029\\202F\\205F\\3000"
    "'"
)

# line breaks and tabs forbidden in single-line text columns
LINE_BREAK_CHARS_SQL = "U&'\\0009\\000A\\000B\\000C\\000D\\0085\\2028\\2029'"


def trimmed_sql(column: str) -> str:
    return f"{column} = btrim({column}, {TRIM_CHARS_SQL})"


def single_line_sql(column: str) -> str:
    return f"{column} = translate({column}, {LINE_BREAK_CHARS_SQL}, '')"
