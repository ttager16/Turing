def is_number_token(s: str) -> bool:
    return bool(RE_NUMBER.match(s))

def match_number_at(text: str, pos: int) -> Optional[Tuple[str, int]]:
    m = re.match(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?', text[pos:])
    if m:
        return m.group(0), pos + m.end()
    return None

def custom_tokenizer(input_text: str) -> List[List[str]]:
    s = input_text.strip()
    n = len(s)
    i = 0
    tokens: List[List[str]] = []
    sent_start = True  # sentence-initial heuristic; consider start and after periods? But periods dropped -> use start and after tokens that ended with period in original? Simpler: sentence-initial only at very start.
    # As periods are dropped except in org suffixes, we treat only absolute start as sentence-initial per spec.
    while i < n:
        # Skip whitespace
        if s[i].isspace():
            i += 1
            continue

        # Attempt multi-token merges (company name, currency value, percentage, currency pair) in order.
        # Save original position for potential fallback
        start = i

        # 1) Company name: Capitalized word followed immediately by an org suffix (org suffix may include period).
        # We need to extract next word and next token possibly separated by single space.
        # Extract next token up to whitespace or punctuation.
        # We'll parse a word (letters with possible internal hyphen?) Spec: Capitalized word (single Latin word).
        # Find next contiguous non-space run as next_word
        j = i
        # collect next "word" token characters until whitespace
        while j < n and not s[j].isspace():
            j += 1
        first = s[i:j]
        # Check capitalization: Capitalized word => starts with uppercase A-Z and has at least one lowercase or any letters
        company_merged = None
        if first and first[0].isupper() and RE_LETTERS.match(first):
            # Lookahead for suffix: there may be a space then suffix or immediately attached?
            k = j
            # skip single space(s)
            while k < n and s[k].isspace():
                k += 1
            # Extract possible suffix token
            m = k
            while m < n and not s[m].isspace():
                m += 1
            suffix = s[k:m] if k < n else ''
            if suffix in ORG_SUFFIXES:
                # Merge first + space(s) + suffix into one token
                merged = s[i:m]
                company_merged = (merged, m)
        if company_merged:
            token_text, new_pos = company_merged
            # Preserve period in suffix as lexicon shows
            tokens.append([token_text, "ENTITY"])
            i = new_pos
            sent_start = False
            continue

        # 2) Currency value: currency symbol + optional space + number + optional space + optional magnitude
        if s[i] in CURRENCY_SYMBOLS:
            # try to parse symbol
            sym = s[i]
            p = i + 1
            # optional space
            while p < n and s[p].isspace():
                p += 1
            num_match = match_number_at(s, p)
            if num_match:
                num_str, p2 = num_match
                q = p2
                # optional space
                while q < n and s[q].isspace():
                    q += 1
                # optional magnitude word
                mag_match = None
                # read next run of letters
                r = q
                while r < n and not s[r].isspace():
                    r += 1
                mag = s[q:r] if q < n else ''
                if mag.lower() in MAGNITUDES:
                    mag_match = mag
                    q = r
                # Build token value preserving original spacing within allowed? Spec: merged span is single token; token text should be the original substring between i and q.
                token_text = s[i:q]
                if num_str:
                    tokens.append([token_text, "VALUE"])
                    i = q
                    sent_start = False
                    continue
        # 3) Percentage: number immediately followed by '%'
        # Check if at position there is number then %
        pct_match = re.match(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(%)', s[i:])
        if pct_match:
            # Ensure % is immediately after number (no spaces)
            numpart = pct_match.group(1)
            pct = pct_match.group(2)
            token_text = numpart + pct
            tokens.append([token_text, "VALUE"])
            i += len(token_text)
            sent_start = False
            continue

        # 4) Currency pair: exactly 3 uppercase letters / 3 uppercase letters
        # We need to check next contiguous non-space run
        j = i
        while j < n and not s[j].isspace():
            j += 1
        run = s[i:j]
        if RE_CURRENCY_PAIR.match(run):
            tokens.append([run, "ENTITY"])
            i = j
            sent_start = False
            continue

        # If no merge applies, extract next token per tokenization rules (split on whitespace)
        # We already have run as next whitespace-delimited chunk
        token = run
        i = j

        # Strip leading/trailing punctuation per rules:
        # - Drop standalone punctuation tokens unless retained by rule (we have no retention here)
        # - Trailing commas: preserve single trailing comma only if base word (without comma) is in discourse marker lexicon (case-sensitive)
        # - Abbreviation periods in org suffixes retained when part of merged token; here single token may be "Inc." standalone but unless merged with capitalized word before, it's just token. The rule says retain period in org suffixes when part of recognized pattern; not elsewhere. So drop periods.
        # Implementation: Check if token is exactly one punctuation char -> drop
        if all(not ch.isalnum() for ch in token):
            # standalone punctuation dropped
            sent_start = False
            continue

        # Handle trailing comma preservation
        preserved_comma = False
        if token.endswith(','):
            base = token[:-1]
            if base in DISCOURSE_MARKERS:
                # preserve single trailing comma
                preserved_comma = True
                token_text = token  # keep comma
            else:
                # strip trailing comma (dropped)
                token = base
        # Remove other punctuation: semicolons, colons, parentheses, standalone periods, and other punctuation are dropped unless covered above.
        # Remove any periods unless token exactly matches an org suffix (which could be here). The org suffixes retention applies only in merges; so drop periods.
        # Also drop any parentheses, semicolons, colons in token by removing them.
        # However, do not remove % or / or currency symbols if part of token (those handled earlier). Here % or / unlikely remain.
        # Remove leading/trailing punctuation chars from token except preserved comma
        def strip_outer_punct(t: str) -> str:
            # Preserve internal punctuation (e.g., USD/EUR handled earlier). Strip leading/trailing chars that are punctuation except if the whole token is discourse marker plus comma handled.
            start = 0
            end = len(t)
            while start < end and not t[start].isalnum() and t[start] not in CURRENCY_SYMBOLS:
                start += 1
            while end > start and not t[end-1].isalnum() and (t[end-1] not in CURRENCY_SYMBOLS) and t[end-1] != ',':
                end -= 1
            return t[start:end]
        if not preserved_comma:
            token = strip_outer_punct(token)
        else:
            # preserve trailing comma but strip other outer punct
            inner = token[:-1]
            inner = strip_outer_punct(inner)
            token = inner + ','

        if token == '':
            sent_start = False
            continue

        # Assign tag using precedence: merges done; now patterns > lexicons > heuristics > OTHER

        tag = None

        # Patterns:
        if RE_PERCENT.match(token):
            tag = "VALUE"
        elif RE_CURRENCY_PAIR.match(token):
            tag = "ENTITY"
        else:
            # Currency value single-token form like "$5" or "$5million"? But currency values with spaces already handled. Here allow symbol attached to number like "$5" or "€1.25"
            if token and token[0] in CURRENCY_SYMBOLS:
                # after symbol there may be number
                rest = token[1:]
                if is_number_token(rest):
                    tag = "VALUE"
                else:
                    # maybe symbol attached to number with magnitude without space: check if rest starts with number then magnitude
                    m = re.match(r'^(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)([A-Za-z]+)?$', rest)
                    if m:
                        mag = m.group(2)
                        if mag and mag.lower() in MAGNITUDES:
                            tag = "VALUE"
            # Company name single-token entity? Single-token company not merged requires capitalized single-token proper nouns in ENTITY_SINGLE
            if not tag and token in ENTITY_SINGLE:
                tag = "ENTITY"

        # Lexicons (exact match, case-sensitive for matching as specified? Lexicons are English words, assume case-sensitive for DET/PREP etc? The spec lists lowercased entries; matching should be exact-match lexicons for English words. Use exact match with case sensitivity as entries are lowercased; tokens preserve case so match case-insensitively for POS lexicons.)
        if not tag:
            low = token.lower()
            if low in PREP:
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
            elif token in DISCOURSE_MARKERS or low in {m.lower() for m in DISCOURSE_MARKERS}:
                tag = "OTHER"
        # Heuristics
        if not tag:
            # Capitalized mixed-case single Latin word not in any lexicon and not sentence-initial => ENTITY.
            if RE_LETTERS.match(token) and token[0].isupper() and not token.isupper() and token not in ENTITY_SINGLE and not sent_start:
                tag = "ENTITY"
        if not tag:
            # Sentence-initial capitalized words are not auto-ENTITY unless in lexicon or merge rule; we've already checked lexicons.
            # Fallback
            tag = "OTHER"

        tokens.append([token, tag])
        sent_start = False

    return tokens