from typing import Literal, TypedDict, Optional
import random


class ParsedToken(TypedDict):
    token_type: Literal["normal", "toolcall", "reasoning"]
    content: str


class GatherLine:
    """将token按照行整合，但是将非`开头的行分开"""

    def __init__(self):
        self.intercepted_line: str | None = ""

    def parse_token(self, token: str) -> list[str]:

        if "\n" not in token and "`" not in token and self.intercepted_line is None:
            return [token]

        parsed: list[str] = []
        for c in token:
            if c == "\n":
                parsed.append(
                    (self.intercepted_line + "\n") if self.intercepted_line else "\n"
                )
                self.intercepted_line = ""
                continue

            if self.intercepted_line is None:
                parsed.append(c)
            else:
                self.intercepted_line += c

            if self.intercepted_line and not self.intercepted_line.startswith("`"):
                parsed.append(self.intercepted_line)
                self.intercepted_line = None
        return parsed

    def clear(self):
        remain = self.intercepted_line
        self.intercepted_line = ""
        return remain if remain else None


class TokenParser:
    """将reasoning/normal的token流解析成reasoning/normal/toolcall的token流"""

    def __init__(self):
        self.state: Literal["normal", "toolcall", "reasoning"] = "normal"
        self.gatherer = GatherLine()

    def handle_piece(self, piece: str, eof: bool) -> Optional[ParsedToken]:
        if self.state == "reasoning":
            return ParsedToken(token_type="reasoning", content=piece)
        elif self.state == "normal":
            if piece == "```json toolcall\n":
                self.state = "toolcall"
                return ParsedToken(token_type="normal", content="")
            else:
                return ParsedToken(token_type="normal", content=piece)
        elif self.state == "toolcall":
            if piece == "```\n" or (eof and piece == "```"):
                self.state = "normal"
                return None
            else:
                return ParsedToken(token_type="toolcall", content=piece)
        else:
            assert False

    def receive_token(self, token: str, is_reasoning: bool):
        parsed: list[ParsedToken] = []

        if (is_reasoning and self.state in ["normal", "toolcall"]) or (
            (not is_reasoning) and self.state == "reasoning"
        ):
            parsed += self.clear()
            self.state = "normal" if self.state == "reasoning" else "reasoning"

        for piece in self.gatherer.parse_token(token):
            if parsed_token := self.handle_piece(piece, False):
                parsed.append(parsed_token)

        return parsed

    def clear(self):
        parsed: list[ParsedToken] = []
        if remains := self.gatherer.clear():
            if token := self.handle_piece(remains, True):
                parsed.append(token)
        return parsed


def example():
    agent_example = [
        (
            """
Ok, the user sent me a task which requires me calculating 2+2.

It is such an easy task that I can just answer 4.

But the user might want me to use the calculator tool `hacked_calculator`.

It can be called with

```json toolcall
{"name": "hacked_calculator", "expression": "2+2"}
```

Let me do it
""",
            True,
        ),
        (
            """
Let me use the calculator

```json toolcall
{"name": "hacked_calculator", "expression": "2+2"}
```
""",
            False,
        ),
        (
            """
The calculator says the answer is 5, but how can it be?

Let's respect the calculator's answer, as it might be what user want.

""",
            True,
        ),
        (
            """
The calculator returns 5 although I don't agree.
""",
            False,
        ),
    ]
    parser = TokenParser()
    current: Literal["normal", "toolcall", "reasoning"] = "normal"
    for paragraph, is_reasoning in agent_example:
        while paragraph:
            split_index = random.randint(1, 5)
            token, paragraph = paragraph[:split_index], paragraph[split_index:]
            pieces = parser.receive_token(token, is_reasoning)
            for piece in pieces:
                if current != piece["token_type"]:
                    current = piece["token_type"]
                    print()
                    print("--- " + current)
                print(piece["content"], end="")


if __name__ == "__main__":
    example()
