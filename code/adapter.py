import collections
import hashlib
import html
import re

from legacy.parser import MarkdownParser


class BodySourceParser(MarkdownParser):
    def __init__(self, legacy_protocol, selection, revision_protocol):
        super().__init__(legacy_protocol, selection)
        self.revision = revision_protocol
        self.known_liquid = set(revision_protocol["adapter"]["known_liquid_tags"])
        self.boundary = "\ufffc"
        self.opener = re.compile(r"<!--|\{%|\{\{|\[!INCLUDE\b|</?[A-Za-z][^<]*?(?=>|$)", re.IGNORECASE)

    def issue(self, diagnostics, name, line, detail=""):
        diagnostics["issue_counts"][name] += 1
        if len(diagnostics["issues"]) < 100:
            diagnostics["issues"].append({"name": name, "line": line, "detail": detail[:160]})
        else:
            diagnostics["omitted_issue_examples"] += 1

    def liquid_marker(self, content, diagnostics, line):
        name_match = re.match(r"[-\s]*([A-Za-z_][A-Za-z_0-9-]*)", content)
        name = name_match.group(1) if name_match else "(invalid)"
        diagnostics["markers"]["liquid_tag"] += 1
        diagnostics["liquid_names"][name] += 1
        if name not in self.known_liquid:
            self.issue(diagnostics, "unknown_liquid_tag", line, name)
        if name == "data":
            if re.search(r"\breusables\.", content):
                diagnostics["markers"]["liquid_reusable"] += 1
            if re.search(r"\bvariables\.", content):
                diagnostics["markers"]["liquid_variable"] += 1
        if name in {"if", "ifversion", "unless", "case", "elsif", "else", "when", "endif", "endunless", "endcase"}:
            diagnostics["markers"]["conditional"] += 1
        if name in {"if", "ifversion", "unless", "case"}:
            diagnostics["_conditional_stack"].append((name, line))
        elif name in {"endif", "endunless", "endcase"}:
            if diagnostics["_conditional_stack"]:
                expected = {"endif": {"if", "ifversion"}, "endunless": {"unless"}, "endcase": {"case"}}[name]
                opening, _ = diagnostics["_conditional_stack"].pop()
                if opening not in expected:
                    self.issue(diagnostics, "conditional_mismatch", line, name + "/" + opening)
            else:
                self.issue(diagnostics, "orphan_conditional_end", line, name)
        if name in {"raw", "endraw"}:
            diagnostics["markers"]["raw_wrapper"] += 1
        if name in {"prompt", "endprompt"}:
            diagnostics["markers"]["prompt_wrapper"] += 1
            if name == "prompt":
                diagnostics["_prompt_stack"].append(line)
            elif diagnostics["_prompt_stack"]:
                diagnostics["_prompt_stack"].pop()
            else:
                self.issue(diagnostics, "orphan_prompt_end", line)
        if name in {"codetabs", "codetab", "endcodetab", "endcodetabs"}:
            diagnostics["markers"]["liquid_code_tab"] += 1

    def mask_plain(self, text, state, diagnostics, line):
        output = []
        position = 0
        while position < len(text):
            if state["kind"]:
                closer = state["closer"]
                if state["kind"] == "include":
                    ending = re.search(r"\)\s*\]", text[position:])
                    end = position + ending.start() if ending else -1
                    width = len(ending.group()) if ending else 0
                else:
                    end = text.find(closer, position)
                    width = len(closer)
                if end < 0:
                    state["content"] += text[position:] + "\n"
                    output.append(self.boundary)
                    return "".join(output)
                state["content"] += text[position:end]
                if state["kind"] == "liquid":
                    self.liquid_marker(state["content"], diagnostics, state["line"])
                output.append(self.boundary)
                position = end + width
                state.update(kind=None, closer=None, content="", line=None)
                continue
            positions = []
            for token, kind, closer in (
                ("<!--", "comment", "-->"), ("{%", "liquid", "%}"),
                ("{{", "output", "}}"), ("[!INCLUDE", "include", ")]")
            ):
                index = text.lower().find(token.lower(), position)
                if index >= 0:
                    positions.append((index, len(token), kind, closer))
            tag = re.search(r"<(?:/?[A-Za-z][A-Za-z0-9:_-]*\b|[!?])", text[position:])
            if tag:
                positions.append((position + tag.start(), 1, "html_tag", ">"))
            if not positions:
                output.append(text[position:])
                break
            index, width, kind, closer = min(positions, key=lambda item: item[0])
            output.append(text[position:index])
            output.append(self.boundary)
            diagnostics["markers"][kind] += 1
            state.update(kind=kind, closer=closer, content="", line=line)
            position = index + width
        return "".join(output)

    def mask_source(self, line, state, diagnostics, number):
        if state["kind"]:
            return self.mask_plain(line, state, diagnostics, number)
        parts = []
        cursor = 0
        for match in self.inline_pattern.finditer(line):
            parts.append(self.mask_plain(line[cursor:match.start()], state, diagnostics, number))
            if state["kind"]:
                parts.append(self.mask_plain(line[match.start():match.end()], state, diagnostics, number))
            else:
                parts.append(match.group())
            cursor = match.end()
        parts.append(self.mask_plain(line[cursor:], state, diagnostics, number))
        return "".join(parts)

    def markup_pair(self, text):
        if "\ufff1" in text or "\ufff2" in text:
            raise ValueError("Reserved inline parser marker in source")
        protected = []
        placeholders = {}
        cursor = 0
        for index, match in enumerate(self.inline_pattern.finditer(text)):
            key = f"\ufff3{index}\ufff4"
            protected.append(text[cursor:match.start()])
            protected.append(key)
            placeholders[key] = match.group(2)
            cursor = match.end()
        protected.append(text[cursor:])
        value = "".join(protected)
        value = re.sub(r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)", self.boundary, value)
        value = re.sub(r"(?<!!)\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)", lambda match: match.group(1), value)
        value = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", lambda match: match.group(1), value)
        value = re.sub(r"https?://[^\s<>]+", self.boundary, value)
        value = re.sub(r"</?[A-Za-z][^>]*>", self.boundary, value)
        value = html.unescape(value)
        value = value.replace("**", "").replace("__", "").replace("*", "")
        value = re.sub(r"(?<!\w)_(?!\s)|(?<!\s)_(?!\w)", "", value)
        for key, literal in placeholders.items():
            value = value.replace(key, "\ufff1" + literal + "\ufff2")
        value = self.normalize(value)
        lexical = []
        prose = []
        inside = False
        for character in value:
            if character == "\ufff1":
                inside = True
            elif character == "\ufff2":
                inside = False
            else:
                lexical.append(character)
                prose.append(self.boundary if inside and not character.isspace() else character)
        lexical = self.normalize("".join(lexical))
        prose = self.normalize("".join(prose))
        if len(lexical) != len(prose):
            raise ValueError("Aligned source-adapter inline mask mismatch")
        return lexical, prose

    def records(self, text, exclude_code=False):
        if any(marker in text for marker in ("\ufff1", "\ufff2", "\ufff3", "\ufff4", "\ufffc")):
            raise ValueError("Reserved source-adapter marker in input")
        lines, generated = self.strip_generated(text.splitlines())
        diagnostics = {
            **generated, "source_lines": len(lines), "frontmatter_lines": 0,
            "code_lines": 0, "quote_lines": 0, "example_lines": 0, "admonition_lines": 0,
            "inline_code_spans": 0, "unclosed_fence": False, "unclosed_html_comment": False,
            "markers": collections.Counter(), "liquid_names": collections.Counter(),
            "issue_counts": collections.Counter(), "issues": [], "omitted_issue_examples": 0,
            "_conditional_stack": [], "_azure_stack": [], "_prompt_stack": []
        }
        front_end = -1
        if lines and lines[0].strip() == "---":
            front_end = next((index for index in range(1, len(lines)) if lines[index].strip() in {"---", "..."}), -1)
            if front_end < 0:
                raise ValueError("Unclosed YAML frontmatter")
            diagnostics["frontmatter_lines"] = front_end + 1
        state = {"kind": None, "closer": None, "content": "", "line": None}
        fence = None
        fence_width = 0
        fence_start = None
        example_level = None
        admonition = False
        records = []
        for index, original in enumerate(lines):
            number = index + 1
            if index <= front_end:
                records.append(None)
                continue
            quote_match = re.match(r"^\s{0,3}(>+)\s?", original)
            quote_depth = len(quote_match.group(1)) if quote_match else 0
            line = original[quote_match.end():] if quote_match else original
            if not quote_match:
                admonition = False
            if fence:
                closing = re.match(r"^\s*([`~]+)\s*$", line)
                if closing and set(closing.group(1)) == {fence} and len(closing.group(1)) >= fence_width:
                    fence = None
                    records.append(None)
                    continue
                kind = "code"
                hard_start = hard_end = False
                diagnostics["markers"]["literal_code_template"] += len(re.findall(r"\{%|\{\{|\[!INCLUDE\b", line))
            else:
                opening = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
                list_marker = re.match(r"^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?", line)
                if opening and not state["kind"]:
                    fence = opening.group(1)[0]
                    fence_width = len(opening.group(1))
                    fence_start = number
                    diagnostics["markers"]["fence_open"] += 1
                    records.append(None)
                    continue
                indented = (
                    not state["kind"] and
                    not list_marker and
                    not quote_match and
                    bool(re.match(r"^(?: {4,}|\t)", original))
                )
                if indented:
                    kind = "code"
                    hard_start = hard_end = False
                    diagnostics["markers"]["literal_code_template"] += len(re.findall(r"\{%|\{\{|\[!INCLUDE\b", line))
                else:
                    directive = re.match(r"^\s*:::\s*([A-Za-z_-]+)?", line)
                    tab = re.match(r"^\s*#{1,6}\s+\[[^\]]+\]\(#tab/[^)]+\)\s*$", line)
                    if directive and not state["kind"]:
                        name = directive.group(1) or "(bare)"
                        diagnostics["markers"]["azure_directive"] += 1
                        diagnostics["markers"]["azure_" + name] += 1
                        if name == "zone" and re.search(r"\bpivot\s*=", line):
                            diagnostics["markers"]["azure_pivot"] += 1
                        if name not in {"zone", "zone-end", "moniker", "moniker-end", "image", "image-end", "code", "row", "row-end", "column", "column-end", "(bare)"}:
                            self.issue(diagnostics, "unknown_azure_directive", number, name)
                        if name in {"zone", "moniker", "row", "column"}:
                            diagnostics["_azure_stack"].append((name, number))
                        elif name in {"zone-end", "moniker-end", "row-end", "column-end"}:
                            if diagnostics["_azure_stack"]:
                                opening_name, _ = diagnostics["_azure_stack"].pop()
                                if opening_name + "-end" != name:
                                    self.issue(diagnostics, "azure_block_mismatch", number, name + "/" + opening_name)
                            else:
                                self.issue(diagnostics, "orphan_azure_block_end", number, name)
                        records.append(None)
                        continue
                    if tab and not state["kind"]:
                        diagnostics["markers"]["azure_tab_selector"] += 1
                        records.append(None)
                        continue
                    admonition_marker = re.match(r"^\s*\[!(NOTE|WARNING|IMPORTANT|TIP|CAUTION)\]\s*", line)
                    if quote_depth == 1 and admonition_marker and not state["kind"]:
                        admonition = True
                        diagnostics["markers"]["admonition_" + admonition_marker.group(1).lower()] += 1
                        line = line[admonition_marker.end():]
                    is_admonition = admonition and quote_depth == 1
                    prompt_before = bool(diagnostics["_prompt_stack"])
                    prompt_markers_before = diagnostics["markers"]["prompt_wrapper"]
                    line = self.mask_source(line, state, diagnostics, number)
                    prompt_context = (
                        prompt_before or
                        bool(diagnostics["_prompt_stack"]) or
                        diagnostics["markers"]["prompt_wrapper"] != prompt_markers_before)
                    heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
                    list_marker = re.match(r"^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?", line)
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
                    kind = "prose"
                    if quote_match and not is_admonition:
                        kind = "quote"
                    elif (example_level is not None or prompt_context) and not is_admonition:
                        kind = "example"
                    hard_start = bool(heading or list_marker or table)
                    hard_end = bool(heading or table)
                    if is_admonition:
                        diagnostics["admonition_lines"] += 1
            if not line.strip():
                records.append(None)
                continue
            if kind != "code" and (
                re.match(r"^\s*\[[^\]]+\]:\s*\S+", line) or
                re.match(r"^\s*(?:\[toc\]|[-=_*]{3,}|\|?[\s:|-]+\|?)\s*$", line, re.I)
            ):
                records.append(None)
                continue
            if kind in {"code", "quote", "example"}:
                diagnostics[kind + "_lines"] += 1
            diagnostics["inline_code_spans"] += len(self.inline_pattern.findall(line))
            if exclude_code and kind != "prose":
                records.append(None)
                continue
            if kind == "code":
                cleaned, masked = self.normalize(line), ""
            else:
                cleaned, masked = self.markup_pair(line)
                if exclude_code:
                    cleaned = self.collapse_code_mask(masked)
                    masked = cleaned
            if not cleaned or not self.words(cleaned):
                records.append(None)
                continue
            records.append({
                "line": number, "text": cleaned,
                "prose_text": masked if kind == "prose" else "",
                "kind": kind, "hard_start": hard_start, "hard_end": hard_end
            })
        if fence:
            diagnostics["unclosed_fence"] = True
            self.issue(diagnostics, "unclosed_fence", fence_start, fence)
        if state["kind"]:
            if state["kind"] == "comment":
                diagnostics["unclosed_html_comment"] = True
            self.issue(diagnostics, "unclosed_" + state["kind"], state["line"])
        for name, number in diagnostics.pop("_conditional_stack"):
            self.issue(diagnostics, "unclosed_conditional", number, name)
        for name, number in diagnostics.pop("_azure_stack"):
            self.issue(diagnostics, "unclosed_azure_block", number, name)
        for number in diagnostics.pop("_prompt_stack"):
            self.issue(diagnostics, "unclosed_prompt_wrapper", number)
        for field in ("markers", "liquid_names", "issue_counts"):
            diagnostics[field] = dict(sorted(diagnostics[field].items()))
        return records, diagnostics

    def normalized_body(self, records):
        return self.normalize(" ".join(record["text"] for record in records if record is not None))

    def body_hash(self, records):
        return hashlib.sha256(self.normalized_body(records).encode("utf-8")).hexdigest()
