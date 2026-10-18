import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata


class MarkdownParser:
    def __init__(self, protocol, selection):
        self.protocol = protocol
        self.selection = selection
        self.words_pattern = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)
        self.inline_pattern = re.compile(r"(`+)(.+?)\1")
        self.trigger_patterns = {}
        for name, phrases in protocol["triggers"].items():
            if not isinstance(phrases, list):
                continue
            alternatives = [
                r"\s+".join(re.escape(word) for word in phrase.split())
                for phrase in sorted(phrases, key=len, reverse=True)
            ]
            self.trigger_patterns[name] = re.compile(
                r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)"
            )

    def normalize(self, text):
        text = unicodedata.normalize("NFKC", text).casefold()
        text = text.translate(str.maketrans({
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'
        }))
        return re.sub(r"\s+", " ", text).strip()

    def sha(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def words(self, text):
        return len(self.words_pattern.findall(text))

    def without_inline_code(self, text):
        return self.inline_pattern.sub("\ufffc", text)

    def markup_pair(self, text):
        text = unicodedata.normalize("NFKC", text)
        if "\ufff1" in text or "\ufff2" in text:
            raise ValueError("Input contains a reserved inline-code parser marker")
        text = self.inline_pattern.sub(
            lambda match: "\ufff1" + match.group(2) + "\ufff2", text
        )
        text = re.sub(r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)", " ", text)
        text = re.sub(
            r"(?<!!)\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)",
            lambda match: match.group(1), text
        )
        text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", lambda match: match.group(1), text)
        text = re.sub(r"https?://[^\s<>\ufff1\ufff2]+", " ", text)
        text = re.sub(r"</?[A-Za-z][^>]*>", " ", text)
        text = html.unescape(text)
        text = text.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
        text = re.sub(r"(?<!\w)_(?!\s)|(?<!\s)_(?!\w)", "", text)
        text = self.normalize(text)
        lexical = []
        prose = []
        inside_code = False
        for character in text:
            if character == "\ufff1":
                inside_code = True
            elif character == "\ufff2":
                inside_code = False
            else:
                lexical.append(character)
                prose.append(
                    "\ufffc" if inside_code and not character.isspace() else character
                )
        lexical = self.normalize("".join(lexical))
        prose = self.normalize("".join(prose))
        if len(lexical) != len(prose):
            raise ValueError("Aligned inline-code mask length mismatch")
        return lexical, prose

    def strip_markup(self, text, remove_inline=False):
        lexical, prose = self.markup_pair(text)
        return self.collapse_code_mask(prose) if remove_inline else lexical

    def collapse_code_mask(self, text):
        return re.sub(r"\ufffc(?:\s*\ufffc)*", "\ufffc", text)

    def strip_generated(self, lines):
        start_pattern = re.compile(self.selection["generated_content"]["region_start_regex"], re.I)
        end_pattern = re.compile(self.selection["generated_content"]["region_end_regex"], re.I)
        inside = False
        regions = 0
        generated_lines = 0
        result = []
        for line in lines:
            if start_pattern.search(line):
                if inside:
                    raise ValueError("Nested generated region")
                inside = True
                regions += 1
            if inside:
                result.append("")
                generated_lines += 1
                if end_pattern.search(line):
                    inside = False
            else:
                result.append(line)
        if inside:
            raise ValueError("Unclosed generated region")
        return result, {"generated_regions": regions, "generated_lines": generated_lines}

    def remove_comment(self, line, inside):
        result = []
        position = 0
        while position < len(line):
            if inside:
                end = line.find("-->", position)
                if end < 0:
                    return "".join(result), True
                inside = False
                position = end + 3
                result.append(" ")
            else:
                start = line.find("<!--", position)
                if start < 0:
                    result.append(line[position:])
                    break
                result.append(line[position:start])
                result.append(" ")
                inside = True
                position = start + 4
        return "".join(result), inside

    def records(self, text, exclude_code=False):
        lines, diagnostics = self.strip_generated(text.splitlines())
        records = []
        inside_comment = False
        frontmatter_end = -1
        if lines and lines[0].strip() == "---":
            for number in range(1, len(lines)):
                if lines[number].strip() in {"---", "..."}:
                    frontmatter_end = number
                    break
            if frontmatter_end < 0:
                raise ValueError("Unclosed YAML front matter")
        fence_character = None
        fence_width = 0
        example_level = None
        diagnostics.update({
            "source_lines": len(lines), "frontmatter_lines": frontmatter_end + 1,
            "code_lines": 0, "quote_lines": 0, "example_lines": 0,
            "inline_code_spans": 0, "unclosed_fence": False,
            "unclosed_html_comment": False
        })
        for index, original in enumerate(lines):
            number = index + 1
            if index <= frontmatter_end:
                records.append(None)
                continue
            line, inside_comment = self.remove_comment(original, inside_comment)
            if fence_character:
                closing = re.match(r"^\s{0,3}([`~]+)\s*$", line)
                if closing and set(closing.group(1)) == {fence_character}:
                    if len(closing.group(1)) >= fence_width:
                        fence_character = None
                        records.append(None)
                        continue
                kind = "code"
                hard_start = False
                hard_end = False
            else:
                opening = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
                if opening:
                    fence_character = opening.group(1)[0]
                    fence_width = len(opening.group(1))
                    records.append(None)
                    continue
                heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
                list_marker = re.match(r"^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?", line)
                quote = re.match(r"^\s{0,3}>\s?", line)
                table = bool(re.match(r"^\s*\|", line))
                if heading:
                    depth = len(heading.group(1))
                    if example_level is not None and depth <= example_level:
                        example_level = None
                    if re.search(r"\b(?:examples?|samples?)\b", heading.group(2), re.I):
                        example_level = depth
                    line = heading.group(2)
                elif list_marker:
                    line = line[list_marker.end():]
                elif quote:
                    line = line[quote.end():]
                kind = "prose"
                if quote:
                    kind = "quote"
                elif not heading and not list_marker and re.match(r"^(?: {4,}|\t)", original):
                    kind = "code"
                elif example_level is not None:
                    kind = "example"
                hard_start = bool(heading or list_marker or table)
                hard_end = bool(heading or table)
            if not line.strip():
                records.append(None)
                continue
            if re.match(r"^\s*\[[^\]]+\]:\s*\S+", line):
                records.append(None)
                continue
            if re.match(r"^\s*(?:\[toc\]|[-=_*]{3,}|\|?[\s:|-]+\|?)\s*$", line, re.I):
                records.append(None)
                continue
            if kind in {"code", "quote", "example"}:
                diagnostics[f"{kind}_lines"] += 1
            diagnostics["inline_code_spans"] += len(self.inline_pattern.findall(line))
            if exclude_code and kind != "prose":
                records.append(None)
                continue
            cleaned, masked = self.markup_pair(line)
            if exclude_code:
                cleaned = self.collapse_code_mask(masked)
                masked = cleaned
            prose_text = masked if kind == "prose" else ""
            if not cleaned or not self.words(cleaned):
                records.append(None)
                continue
            records.append({
                "line": number, "text": cleaned, "prose_text": prose_text,
                "kind": kind, "hard_start": hard_start, "hard_end": hard_end
            })
        diagnostics["unclosed_fence"] = fence_character is not None
        diagnostics["unclosed_html_comment"] = inside_comment
        return records, diagnostics

    def blocks(self, records):
        current = []
        for record in records:
            if record is None:
                if current:
                    yield current
                    current = []
                continue
            new_kind = current and record["kind"] != current[-1]["kind"]
            previous_ended = current and current[-1]["hard_end"]
            if current and (record["hard_start"] or new_kind or previous_ended):
                yield current
                current = []
            current.append(record)
        if current:
            yield current

    def sentence_spans(self, text):
        protected = re.sub(
            r"\b(?:e\.g\.|i\.e\.|mr\.|mrs\.|dr\.|vs\.|etc\.)",
            lambda match: match.group().replace(".", "\ufff0"), text
        )
        start = 0
        for match in re.finditer(r"[.!?]+(?:[\"')\]]+)?(?=\s|$)", protected):
            end = match.end()
            if text[start:end].strip():
                yield start, end
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
        if text[start:].strip():
            yield start, len(text)

    def make_unit(self, records, text=None, start=None, end=None, prose_text=None):
        if text is None:
            text = " ".join(record["text"] for record in records)
        kind = records[0]["kind"]
        if prose_text is None:
            prose_text = " ".join(record["prose_text"] for record in records)
        return {
            "text": self.normalize(text),
            "text_sha256": self.sha(self.normalize(text)),
            "kind": kind,
            "start_line": start or records[0]["line"],
            "end_line": end or records[-1]["line"],
            "context_block_start": records[0]["line"],
            "context_block_end": records[-1]["line"],
            "eligible_words": self.words(text),
            "prose_words": self.words(prose_text) if kind == "prose" else 0,
            "prose_text": prose_text if kind == "prose" else ""
        }

    def units(self, records, segmentation):
        ordinal = 0
        for block in self.blocks(records):
            if segmentation == "line" or segmentation == "sentence" and block[0]["kind"] == "code":
                candidates = [self.make_unit([record]) for record in block]
                for candidate in candidates:
                    candidate["context_block_start"] = block[0]["line"]
                    candidate["context_block_end"] = block[-1]["line"]
            elif segmentation == "paragraph":
                candidates = [self.make_unit(block)]
            else:
                text = " ".join(record["text"] for record in block)
                positions = []
                cursor = 0
                for record in block:
                    positions.append((cursor, cursor + len(record["text"]), record))
                    cursor += len(record["text"]) + 1
                candidates = []
                for start, end in self.sentence_spans(text):
                    participating = [
                        record for low, high, record in positions
                        if low < end and high > start
                    ]
                    sentence = text[start:end].strip()
                    if block[0]["kind"] == "prose":
                        prose_joined = " ".join(record["prose_text"] for record in block)
                        if len(prose_joined) != len(text):
                            raise ValueError("Sentence prose-mask alignment failure")
                        prose_sentence = prose_joined[start:end]
                    else:
                        prose_sentence = ""
                    candidate = self.make_unit(
                        participating, text=sentence,
                        prose_text=prose_sentence
                    )
                    candidate["context_block_start"] = block[0]["line"]
                    candidate["context_block_end"] = block[-1]["line"]
                    candidates.append(candidate)
            for candidate in candidates:
                if not candidate["text"] or not candidate["eligible_words"]:
                    continue
                ordinal += 1
                candidate["ordinal"] = ordinal
                yield candidate

    def matches(self, unit, triggers):
        p_matches = self.trigger_patterns[f"{triggers}_prohibition"].findall(unit["text"])
        o_matches = self.trigger_patterns[f"{triggers}_obligation"].findall(unit["text"])
        return bool(p_matches), bool(o_matches), sorted(set(p_matches)), sorted(set(o_matches))

    def identity(self, corpus, pin, path, segmentation, unit):
        return self.sha("|".join(str(value) for value in (
            corpus, pin, path, segmentation, unit["start_line"],
            unit["end_line"], unit["ordinal"], unit["text_sha256"]
        )))

    def load(self, path, exclude_code=False):
        return self.records(Path(path).read_text(encoding="utf-8-sig", errors="strict"), exclude_code)


if __name__ == "__main__":
    root = Path(__file__).parent
    parser = MarkdownParser(
        json.loads((root / "protocol.json").read_text(encoding="utf-8")),
        json.loads((root / "selection.json").read_text(encoding="utf-8"))
    )
    raise SystemExit("Library only; run owned toy tests or the guarded analysis")
