import json
import re
import shlex

from common import ROOT


class Risk:
    def __init__(self):
        self.lex = json.loads((ROOT / "risk-lexicon-frozen.json").read_text())
        self.rules = [(r, re.compile(r["regex"], 0 if r.get("case_sensitive") else re.I))
                      for r in self.lex["command_rules"]]
        self.verbs = {k: re.compile(v, re.I) for k, v in self.lex["prose_description_verbs"].items()}
        self.known = set(self.lex["primary_source"]["known_cli"])
        self.allowed = set(self.lex["primary_source"]["shell_info"] + self.lex["primary_source"]["sql_info"])

    def clean(self, text):
        text = text.strip()
        text = re.sub(r"^PS\s+[^>]*>\s*", "", text, flags=re.I)
        text = re.sub(r"^(?:[$>]\s+)", "", text)
        text = re.sub(r"^(?:sudo|command|exec|time|nohup)\s+", "", text)
        text = re.sub(r"^(?:[A-Za-z_][A-Za-z_0-9]*=\S+\s+)+", "", text)
        return text.strip()

    def segments(self, line):
        parts = []
        current = []
        quote = None
        i = 0
        while i < len(line):
            c = line[i]
            if c in {"'", '"'}:
                if quote is None:
                    quote = c
                elif quote == c:
                    quote = None
            if quote is None and c in {";", "|", "&"}:
                parts.append("".join(current))
                current = []
                while i + 1 < len(line) and line[i + 1] == c:
                    i += 1
            else:
                current.append(c)
            i += 1
        parts.append("".join(current))
        return [self.clean(p) for p in parts if p.strip()]

    def command(self, line, source="code", number=None):
        raw = line.strip()
        if not raw or raw.startswith(("#", "//", "--", "/*", "* ")):
            return []
        matches = []
        for segment in self.segments(line):
            for rule, pattern in self.rules:
                if pattern.search(segment):
                    matches.append({"tier": rule["tier"], "rule": rule["id"], "command": segment,
                                    "raw_line": line, "line": number, "source": source})
        return matches

    def highest(self, matches):
        tiers = {m["tier"] for m in matches}
        return "D" if "D" in tiers else "W" if "W" in tiers else "R"

    def verb_matches(self, text, source, number=None):
        return [{"tier": tier, "rule": "verb-" + tier, "command": m.group(), "raw_line": text,
                 "line": number, "source": source}
                for tier, pattern in self.verbs.items() for m in pattern.finditer(text)]

    def blocks(self, text):
        lines = text.splitlines()
        start = 0
        if lines and lines[0].strip() == "---":
            start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), 0)
        blocks = []
        active = None
        occupied = set(range(start))
        in_comment = False
        for i in range(start, len(lines)):
            raw = lines[i]
            stripped = re.sub(r"^\s{0,3}>+\s?", "", raw)
            opening = re.match(r"^\s*(`{3,}|~{3,})\s*(.*)$", stripped)
            if active and active["kind"] == "fenced":
                occupied.add(i)
                if opening and opening.group(1)[0] == active["fence"] and len(opening.group(1)) >= active["width"] and not opening.group(2):
                    active = None
                else:
                    blocks[-1]["lines"].append((i + 1, stripped))
                continue
            if active and active["kind"] == "indented":
                if re.match(r"^(?: {4,}|\t)", raw) or not raw.strip():
                    blocks[-1]["lines"].append((i + 1, raw.lstrip()))
                    occupied.add(i)
                    continue
                active = None
            if in_comment:
                occupied.add(i)
                if "-->" in raw:
                    in_comment = False
                continue
            if "<!--" in raw:
                occupied.add(i)
                if "-->" not in raw[raw.index("<!--") + 4:]:
                    in_comment = True
                continue
            if opening:
                info = opening.group(2).split()[0].casefold() if opening.group(2).strip() else ""
                info = info.strip("{}.").lstrip(".")
                active = {"kind": "fenced", "info": info, "fence": opening.group(1)[0],
                          "width": len(opening.group(1)), "start_line": i + 1, "lines": []}
                blocks.append(active)
                occupied.add(i)
            elif re.match(r"^(?: {4,}|\t)", raw):
                active = {"kind": "indented", "info": "", "start_line": i + 1,
                          "lines": [(i + 1, raw.lstrip())]}
                blocks.append(active)
                occupied.add(i)
        outside = [(i + 1, s) for i, s in enumerate(lines) if i not in occupied]
        return blocks, outside

    def qualifies_unlabeled(self, line):
        normalized = self.clean(line)
        token = normalized.split(None, 1)[0].casefold() if normalized else ""
        return bool(re.match(r"^\s*[$>]\s+", line) or token in self.known or token.startswith("mkfs."))

    def extract(self, text, description=""):
        blocks, outside = self.blocks(text)
        primary = []
        allcode = []
        inline = []
        for block in blocks:
            for line, value in block["lines"]:
                found = self.command(value, "code:" + (block["info"] or "unlabeled"), line)
                allcode.extend(found)
                if block["info"] in self.allowed or (not block["info"] and self.qualifies_unlabeled(value)):
                    primary.extend(found)
        for line, value in outside:
            for match in re.finditer(r"(`+)(.+?)\1", value):
                inline.extend(self.command(match.group(2), "inline", line))
        desc = self.verb_matches(description or "", "description")
        cov = {
            "steps": sum(bool(re.match(r"^\s*(?:>\s*)?\d+[.)]\s+", value)) for _, value in outside),
            "headings": sum(bool(re.match(r"^\s{0,3}#{1,6}\s+", value)) for _, value in outside),
            "code_blocks": len(blocks)
        }
        return {
            "primary_tier": self.highest(primary), "primary_matches": primary,
            "V-allcode": self.highest(allcode), "V-allcode_matches": allcode,
            "V-inline": self.highest(primary + inline), "V-inline_matches": primary + inline,
            "V-desc": self.highest(desc), "V-desc_matches": desc, **cov
        }

    def tests(self):
        failures = []
        for case in self.lex["negative_cases"]:
            found = self.highest(self.command(case["text"]))
            if found != case["expected"]:
                failures.append({"case": case, "actual": found})
        primary = self.extract("Never use `rm -rf work`.\n")
        if (primary["primary_tier"], primary["V-inline"]) != ("R", "D"):
            failures.append({"case": "inline prohibition cannot set primary", "actual": primary})
        if self.extract("```python\nrm -rf work\n```")["primary_tier"] != "R":
            failures.append({"case": "python block excluded from primary"})
        if self.extract("```\nrm -rf work\n```")["primary_tier"] != "D":
            failures.append({"case": "unlabeled CLI block accepted"})
        if failures:
            raise ValueError("Risk fixture failures: " + json.dumps(failures))
        return {"passed": True, "lexicon_cases": len(self.lex["negative_cases"]),
                "source_eligibility_cases": 3, "human_annotation": False}
