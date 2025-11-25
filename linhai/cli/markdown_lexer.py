"""
copy and paste from pygments: pygments/lexers/markup.py
"""

import re

from pygments.lexer import (
    RegexLexer,
    include,
    bygroups,
    using,
    this,
)
from pygments.token import (
    Text,
    Keyword,
    Name,
    String,
    Generic,
    Whitespace,
)
from pygments.util import get_bool_opt, ClassNotFound
from pygments.token import String


class EnhancedMarkdownLexer(RegexLexer):
    """
    For Markdown markup.
    """

    name = "Markdown"
    url = "https://daringfireball.net/projects/markdown/"
    aliases = ["markdown", "md"]
    filenames = ["*.md", "*.markdown"]
    mimetypes = ["text/x-markdown"]
    version_added = "2.2"
    flags = re.MULTILINE

    def _handle_codeblock(self, match):
        from pygments.lexers import get_lexer_by_name

        yield match.start("initial"), String.Backtick, match.group("initial")
        yield match.start("lang"), String.Backtick, match.group("lang")
        if match.group("afterlang") is not None:
            yield match.start("whitespace"), Whitespace, match.group("whitespace")
            yield match.start("extra"), Text, match.group("extra")
        yield match.start("newline"), Whitespace, match.group("newline")

        lexer = None
        if self.handlecodeblocks:
            try:
                lexer = get_lexer_by_name(match.group("lang").strip())
            except ClassNotFound:
                pass
        code = match.group("code")

        if lexer is None:
            yield match.start("code"), String, code
        else:
            yield from lexer.get_tokens_unprocessed(code)

        yield match.start("terminator"), String.Backtick, match.group("terminator")

    tokens = {
        "root": [
            (r"(^#[^#].+)(\n)", bygroups(Generic.Heading, Text)),
            (r"(^#{2,6}[^#].+)(\n)", bygroups(Generic.Subheading, Text)),
            (
                r"^(.+)(\n)(=+)(\n)",
                bygroups(Generic.Heading, Text, Generic.Heading, Text),
            ),
            (
                r"^(.+)(\n)(-+)(\n)",
                bygroups(Generic.Subheading, Text, Generic.Subheading, Text),
            ),
            (
                r"^(\s*)([*-] )(\[[ xX]\])( .+\n)",
                bygroups(Whitespace, Keyword, Keyword, using(this, state="inline")),
            ),
            (
                r"^(\s*)([*-])(\s)(.+\n)",
                bygroups(Whitespace, Keyword, Whitespace, using(this, state="inline")),
            ),
            (
                r"^(\s*)([0-9]+\.)( .+\n)",
                bygroups(Whitespace, Keyword, using(this, state="inline")),
            ),
            (r"^(\s*>\s)(.+\n)", bygroups(Keyword, Generic.Emph)),
            (r"^(\s*`{3,}\n[\w\W]*?^\s*`{3,}$\n)", String.Backtick),
            (
                r"""(?x)
              ^(?P<initial>\s*`{3,})
              (?P<lang>[\w\-]+)
              (?P<afterlang>
                 (?P<whitespace>[^\S\n]+)
                 (?P<extra>.*))?
              (?P<newline>\n)
              (?P<code>(.|\n)*?)
              (?P<terminator>^\s*`{3,}$\n)
              """,
                _handle_codeblock,
            ),
            include("inline"),
        ],
        "inline": [
            (r"\\.", Text),
            (r"([^`]?)(`[^`\n]+`)", bygroups(Text, String.Backtick)),
            (r"([^\*]?)(\*\*[^* \n][^*\n]*\*\*)", bygroups(Text, Generic.Strong)),
            (r"([^_]?)(__[^_ \n][^_\n]*__)", bygroups(Text, Generic.Strong)),
            (r"([^\*]?)(\*[^* \n][^*\n]*\*)", bygroups(Text, Generic.Emph)),
            (r"([^_]?)(_[^_ \n][^_\n]*_)", bygroups(Text, Generic.Emph)),
            (r"([^~]?)(~~[^~ \n][^~\n]*~~)", bygroups(Text, Generic.Deleted)),
            (r"[@#][\w/:]+", Name.Entity),
            (
                r"(!?\[)([^]]+)(\])(\()([^)]+)(\))",
                bygroups(Text, Name.Tag, Text, Text, Name.Attribute, Text),
            ),
            (
                r"(\[)([^]]+)(\])(\[)([^]]*)(\])",
                bygroups(Text, Name.Tag, Text, Text, Name.Label, Text),
            ),
            (
                r"^(\s*\[)([^]]*)(\]:\s*)(.+)",
                bygroups(Text, Name.Label, Text, Name.Attribute),
            ),
            (r"[^\\\s]+", Text),
            (r".", Text),
        ],
    }

    def __init__(self, **options):
        self.handlecodeblocks = get_bool_opt(options, "handlecodeblocks", True)
        RegexLexer.__init__(self, **options)
