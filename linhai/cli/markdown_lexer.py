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

        # lookup lexer if wanted and existing
        lexer = None
        if self.handlecodeblocks:
            try:
                lexer = get_lexer_by_name(match.group("lang").strip())
            except ClassNotFound:
                pass
        code = match.group("code")
        # no lexer for this language. handle it like it was a code block
        if lexer is None:
            yield match.start("code"), String, code
        else:
            yield from lexer.get_tokens_unprocessed(code)

        yield match.start("terminator"), String.Backtick, match.group("terminator")

    tokens = {
        "root": [
            # heading with '#' prefix (atx-style)
            (r"(^#[^#].+)(\n)", bygroups(Generic.Heading, Text)),
            # subheading with '#' prefix (atx-style)
            (r"(^#{2,6}[^#].+)(\n)", bygroups(Generic.Subheading, Text)),
            # heading with '=' underlines (Setext-style)
            (
                r"^(.+)(\n)(=+)(\n)",
                bygroups(Generic.Heading, Text, Generic.Heading, Text),
            ),
            # subheading with '-' underlines (Setext-style)
            (
                r"^(.+)(\n)(-+)(\n)",
                bygroups(Generic.Subheading, Text, Generic.Subheading, Text),
            ),
            # task list
            (
                r"^(\s*)([*-] )(\[[ xX]\])( .+\n)",
                bygroups(Whitespace, Keyword, Keyword, using(this, state="inline")),
            ),
            # bulleted list
            (
                r"^(\s*)([*-])(\s)(.+\n)",
                bygroups(Whitespace, Keyword, Whitespace, using(this, state="inline")),
            ),
            # numbered list
            (
                r"^(\s*)([0-9]+\.)( .+\n)",
                bygroups(Whitespace, Keyword, using(this, state="inline")),
            ),
            # quote
            (r"^(\s*>\s)(.+\n)", bygroups(Keyword, Generic.Emph)),
            # code block fenced by 3 backticks
            (r"^(\s*`{3,}\n[\w\W]*?^\s*`{3,}$\n)", String.Backtick),
            # code block with language
            # Some tools include extra stuff after the language name, just
            # highlight that as text. For example: https://docs.enola.dev/use/execmd
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
            # escape
            (r"\\.", Text),
            # inline code
            (r"([^`]?)(`[^`\n]+`)", bygroups(Text, String.Backtick)),
            # warning: the following rules eat outer tags.
            # eg. **foo _bar_ baz** => foo and baz are not recognized as bold
            # bold fenced by '**'
            (r"([^\*]?)(\*\*[^* \n][^*\n]*\*\*)", bygroups(Text, Generic.Strong)),
            # bold fenced by '__'
            (r"([^_]?)(__[^_ \n][^_\n]*__)", bygroups(Text, Generic.Strong)),
            # italics fenced by '*'
            (r"([^\*]?)(\*[^* \n][^*\n]*\*)", bygroups(Text, Generic.Emph)),
            # italics fenced by '_'
            (r"([^_]?)(_[^_ \n][^_\n]*_)", bygroups(Text, Generic.Emph)),
            # strikethrough
            (r"([^~]?)(~~[^~ \n][^~\n]*~~)", bygroups(Text, Generic.Deleted)),
            # mentions and topics (twitter and github stuff)
            (r"[@#][\w/:]+", Name.Entity),
            # (image?) links eg: ![Image of Yaktocat](https://octodex.github.com/images/yaktocat.png)
            (
                r"(!?\[)([^]]+)(\])(\()([^)]+)(\))",
                bygroups(Text, Name.Tag, Text, Text, Name.Attribute, Text),
            ),
            # reference-style links, e.g.:
            #   [an example][id]
            #   [id]: http://example.com/
            (
                r"(\[)([^]]+)(\])(\[)([^]]*)(\])",
                bygroups(Text, Name.Tag, Text, Text, Name.Label, Text),
            ),
            (
                r"^(\s*\[)([^]]*)(\]:\s*)(.+)",
                bygroups(Text, Name.Label, Text, Name.Attribute),
            ),
            # general text, must come last!
            (r"[^\\\s]+", Text),
            (r".", Text),
        ],
    }

    def __init__(self, **options):
        self.handlecodeblocks = get_bool_opt(options, "handlecodeblocks", True)
        RegexLexer.__init__(self, **options)
