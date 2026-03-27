def _is_number(s: str) -> bool:
    return bool(_number_re.match(s))

def _match_currency_pair(s: str) -> bool:
    return bool(_currency_pair_re.match(s))

def _match_percentage(s: str) -> bool:
    return bool(_percentage_re.match(s))

def _match_currency_value_tokens(parts: List[str], start: int) -> Optional[Tuple[int, str]]:
    # Attempt to match currency symbol + number + optional magnitude, allowing spaces
    if start >= len(parts):
        return None
    p0 = parts[start]
    # currency symbol possibly attached to number e.g. "$5" or "$5" with no space
    # handle attached cases first
    # Case A: single token like "$5" or "$5.0" or "$1,000" or "$5million" (magnitude must be separate per rules) -> allow "$5" or "$5" + magnitude
    # But rule says currency symbol attached to a number and optional magnitude (whitespace allowed)
    # So we accept "$5", "$5 million", "$5million" only if number part matches when removing symbol.
    if p0 and p0[0] in CURRENCY_SYMBOLS:
        rest = p0[1:]
        if rest != "":
            # attached number
            if _is_number(rest):
                end = start + 1
                # check next token for magnitude
                if end < len(parts) and parts[end].lower() in MAGNITUDES:
                    end += 1
                tok = " ".join(parts[start:end])
                # normalize spaces around symbol: keep as original join (per tokenization, symbol attached allowed)
                return end, tok
    # Case B: symbol as separate token
    if p0 in CURRENCY_SYMBOLS:
        if start + 1 < len(parts):
            p1 = parts[start + 1]
            if _is_number(p1):
                end = start + 2
                if end < len(parts) and parts[end].lower() in MAGNITUDES:
                    end += 1
                tok = " ".join(parts[start:end])
                return end, tok
    return None

def custom_tokenizer(input_text: str) -> List[List[str]]:
    text = input_text.strip()
    parts = []  # initial split on whitespace, preserving original tokens
    if text == "":
        return []
    raw_parts = text.split()
    # Preprocess trailing commas: preserve single trailing comma only if base word is in discourse markers (case-sensitive)
    for rp in raw_parts:
        if rp.endswith(",") and len(rp) > 1:
            base = rp[:-1]
            if base in DISCOURSE_MARKERS:
                parts.append(rp)  # keep comma attached
            else:
                parts.append(base)
        else:
            parts.append(rp)
    tokens: List[List[str]] = []
    i = 0
    sentence_initial = True
    while i < len(parts):
        # At each position, attempt merges in order
        # 1) Company name: Capitalized word followed immediately by org suffix
        # Check current token possibly with punctuation removed per rules: org suffix may include period retained.
        cur = parts[i]
        # For matching company name, need capitalized word (first char uppercase, others any) and next token equals one of ORG_SUFFIXES possibly attached?
        if i + 1 < len(parts):
            next_tok = parts[i + 1]
            # next_tok may include trailing punctuation? Per tokenization semicolons/colons/periods dropped unless org suffix includes period. We kept raw tokens with punctuation removed except discourse commas.
            # So match next_tok exactly to ORG_SUFFIXES
            if next_tok in ORG_SUFFIXES and len(cur) > 0 and cur[0].isupper() and cur.isalpha():
                merged = cur + " " + next_tok
                tokens.append([merged, "ENTITY"])
                i += 2
                sentence_initial = False
                continue
        # 2) Currency value merge
        m_cv = _match_currency_value_tokens(parts, i)
        if m_cv:
            end, tok = m_cv
            # Tokenization rule: preserve as single token; ensure formatting like "$5 million" keeps space if present
            tokens.append([tok, "VALUE"])
            i = end
            sentence_initial = False
            continue
        # 3) Percentage merge: number immediately followed by "%" in same token OR number token with trailing % attached
        cur_raw = parts[i]
        if _match_percentage(cur_raw):
            tokens.append([cur_raw, "VALUE"])
            i += 1
            sentence_initial = False
            continue
        # 4) Currency pair merge
        if _match_currency_pair(cur_raw):
            tokens.append([cur_raw, "ENTITY"])
            i += 1
            sentence_initial = False
            continue
        # If no merge, extract next token per tokenization rules
        # Strip standalone punctuation tokens unless explicitly retained
        tok = cur_raw
        # Drop standalone punctuation tokens: tokens that are entirely punctuation (excluding discourse comma which we preserved attached)
        if all((not ch.isalnum()) for ch in tok):
            i += 1
            # do not change sentence_initial if only punctuation dropped
            continue
        # Strip trailing punctuation: periods, semicolons, colons, parentheses etc.
        # Preserve abbreviation periods in org suffixes only when token equals an org suffix; those would have matched earlier in company merge but single-token org suffix should be dropped/treated?
        # Rule: Abbreviation period in organization suffixes retained when part of recognized pattern. Else periods dropped.
        # So if token equals an org suffix alone (unlikely), keep as is; otherwise remove trailing periods etc.
        if tok not in ORG_SUFFIXES:
            # Remove trailing periods, semicolons, colons, parentheses
            tok = tok.rstrip('.;:()')
        # Trailing comma was already handled in preprocessing; keep it only if discourse marker preserved (it would be in DISCOURSE_MARKERS with comma)
        # Now assign tag using precedence
        tag = None
        # Patterns (ENTITY patterns, VALUE patterns)
        if _match_currency_pair(tok):
            tag = "ENTITY"
        elif _match_percentage(tok):
            tag = "VALUE"
        else:
            # Lexicons (exact matches). Tagging is case-sensitive for some sets? Lexicons are given lowercase words; matching should be exact-match lexicons for English words -> assume case-sensitive as listed; but examples use lowercase tokens.
            low = tok.lower()
            if tok in ENTITY_LEX:
                tag = "ENTITY"
            elif tok in PREP:
                tag = "PREP"
            elif tok in DET:
                tag = "DET"
            elif tok in ADJ:
                tag = "ADJ"
            elif tok in VERB:
                tag = "VERB"
            elif tok in NOUN:
                tag = "NOUN"
            elif tok in TIME:
                tag = "TIME"
            elif low in PREP:
                tag = "PREP"
            elif low in DET:
                tag = "DET"
            elif low in ADJ:
                tag = "ADJ"
            elif low in VERB:
                tag = "VERB"
            elif low in NOUN:
                tag = "NOUN"
            elif low in TIME:
                tag = "TIME"
        # Discourse markers: tagging is case-insensitive per spec, but preservation rule is case-sensitive earlier. So tag as OTHER if matches discourse marker ignoring case.
        if tag is None and tok.rstrip(",") .lower() in {m.lower() for m in DISCOURSE_MARKERS}:
            tag = "OTHER"
        # Heuristics
        if tag is None:
            # Capitalized mixed-case single Latin word not in any lexicon and not sentence-initial: tag ENTITY.
            # Mixed-case meaning starts with uppercase and has lowercase letters (i.e., not all upper)
            if (not sentence_initial) and re.match(r'^[A-Za-z]+$', tok) and tok[0].isupper() and not tok.isupper() and tok not in ENTITY_LEX:
                tag = "ENTITY"
            else:
                tag = "OTHER"
        tokens.append([tok, tag])
        i += 1
        sentence_initial = False
    return tokens