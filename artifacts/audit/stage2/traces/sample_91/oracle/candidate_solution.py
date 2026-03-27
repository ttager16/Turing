from typing import List, Tuple, Optional

def custom_tokenizer(input_text: str) -> List[List[str]]:
    # Lexicons and constants (closed sets, deterministic)
    ORG_SUFFIXES = {
        "Inc.", "Corp.", "Corporation", "Ltd.", "PLC", "AG", "SA", "NV", "LLC", "LP", "Co.", "Company"
    }
    DISCOURSE_MARKERS_PRESERVE = {"Meanwhile"}  # case-sensitive for comma preservation
    DISCOURSE_MARKERS_LOWER = {w.lower() for w in DISCOURSE_MARKERS_PRESERVE}  # for tagging (case-insensitive)

    PREP = {"with", "in", "on", "at", "by", "for", "to", "of", "from", "over", "under", "between"}
    DET = {"the", "a", "an", "this", "that", "these", "those"}
    ADJ = {"strong", "first"}
    VERB = {"surprises", "surging", "climbs"}
    NOUN = {"investors", "profits", "demand"}
    TIME = {"hour", "day", "week", "month", "year"}
    ENTITY_SINGLE = {"NetSky"}

    MAGNITUDES = {"thousand", "million", "billion", "trillion"}  # case-insensitive
    CURRENCY_SYMBOLS = {"$", "€", "£", "¥"}

    SENTENCE_ENDERS = {".", "!", "?"}
    # Punctuation to strip from ends (trailing/leading) unless specified otherwise
    TRAIL_STRIP = set(";:)]}!?")
    LEAD_STRIP = set("([{\"\u201c\u201d'")  # include common quotes

    s = input_text.strip()
    n = len(s)
    out: List[List[str]] = []
    i = 0
    sentence_start = True  # track sentence-initial status for heuristics

    # Utilities
    def is_upper_alpha(c: str) -> bool:
        return "A" <= c <= "Z"

    def is_lower_alpha(c: str) -> bool:
        return "a" <= c <= "z"

    def is_alpha(c: str) -> bool:
        return is_upper_alpha(c) or is_lower_alpha(c)

    def skip_spaces(idx: int) -> int:
        while idx < n and s[idx].isspace():
            idx += 1
        return idx

    def match_number(idx: int) -> Optional[int]:
        # number: digits, optionally with proper thousands separators and optional decimal part
        j = idx
        if j >= n or not s[j].isdigit():
            return None
        # initial digits
        while j < n and s[j].isdigit():
            j += 1
        # optional thousands groups
        k = j
        if k < n and s[k] == ",":
            # require groups of ',' followed by exactly three digits repeatedly
            while k < n and s[k] == ",":
                if k + 3 >= n or not (s[k+1].isdigit() and s[k+2].isdigit() and s[k+3].isdigit()):
                    # invalid grouping; end number before the comma
                    k = j
                    break
                k += 4  # skip ',' and 3 digits
            j = k
        # optional decimal part
        if j < n and s[j] == ".":
            j2 = j + 1
            if j2 < n and s[j2].isdigit():
                while j2 < n and s[j2].isdigit():
                    j2 += 1
                j = j2
            # else no digits after '.', ignore decimal point (treat '.' as punctuation)
        return j

    def match_word_letters(idx: int) -> Optional[int]:
        j = idx
        if j >= n or not is_alpha(s[j]):
            return None
        while j < n and is_alpha(s[j]):
            j += 1
        return j

    def match_company_merge(idx: int) -> Optional[Tuple[str, str, int]]:
        # Capitalized word (A-Z followed by at least one a-z) + spaces + org suffix
        j = idx
        if j >= n or not is_upper_alpha(s[j]):
            return None
        j += 1
        # require at least one lowercase letter next
        if j >= n or not is_lower_alpha(s[j]):
            return None
        # consume rest of the word (letters only)
        while j < n and is_alpha(s[j]):
            j += 1
        # now spaces
        k = skip_spaces(j)
        # try each suffix (exact match, with boundary)
        for suf in ORG_SUFFIXES:
            L = len(suf)
            if k + L <= n and s.startswith(suf, k):
                end = k + L
                # boundary after suffix: not a letter (so "PLCx" doesn't match)
                after = s[end] if end < n else ""
                if end == n or not is_alpha(after):
                    token_text = s[idx:end]
                    return (token_text, "ENTITY", end)
        return None

    def match_currency_value(idx: int) -> Optional[Tuple[str, str, int]]:
        # currency symbol + optional space + number + optional space + optional magnitude
        if s[idx] not in CURRENCY_SYMBOLS:
            return None
        j = idx + 1
        j = skip_spaces(j)
        num_end = match_number(j)
        if num_end is None:
            return None
        k = num_end
        k_ws = skip_spaces(k)
        # optional magnitude (letters only, case-insensitive)
        mag_end = match_word_letters(k_ws)
        end = num_end
        if mag_end is not None:
            word = s[k_ws:mag_end]
            if word.lower() in MAGNITUDES:
                end = mag_end
            else:
                end = num_end
        else:
            end = num_end
        token_text = s[idx:end]
        return (token_text, "VALUE", end)

    def match_percentage(idx: int) -> Optional[Tuple[str, str, int]]:
        num_end = match_number(idx)
        if num_end is None:
            return None
        if num_end < n and s[num_end] == "%":
            token_text = s[idx:num_end+1]
            return (token_text, "VALUE", num_end+1)
        return None

    def match_currency_pair(idx: int) -> Optional[Tuple[str, str, int]]:
        if idx + 7 <= n:
            a = s[idx:idx+3]
            b = s[idx+3]
            c = s[idx+4:idx+7]
            if all(is_upper_alpha(ch) for ch in a) and b == "/" and all(is_upper_alpha(ch) for ch in c):
                token_text = s[idx:idx+7]
                return (token_text, "ENTITY", idx+7)
        return None

    def next_raw_token(idx: int) -> Tuple[str, int]:
        j = idx
        while j < n and not s[j].isspace():
            j += 1
        return s[idx:j], j

    def strip_and_preserve_punct(raw: str) -> Tuple[str, bool]:
        # Returns (clean_token, ended_sentence_flag)
        if not raw:
            return "", False

        # track if we removed a sentence ender
        ended_sentence = False

        # remove leading brackets/quotes
        start = 0
        end = len(raw)

        while start < end and raw[start] in LEAD_STRIP:
            start += 1

        t = raw[start:end]

        # Special case: if token exactly equals org suffix with period, preserve the period
        if t in ORG_SUFFIXES:
            # still may handle trailing commas beyond suffix, but org suffixes include only letters/period
            return t, False

        # handle trailing commas: preserve a single trailing comma ONLY for discourse markers
        # count trailing commas
        comma_count = 0
        k = len(t) - 1
        while k >= 0 and t[k] == ",":
            comma_count += 1
            k -= 1
        if comma_count > 0:
            base = t[:len(t) - comma_count]
            # preserve exactly one comma if base is discourse marker (case-sensitive for preservation)
            if base in DISCOURSE_MARKERS_PRESERVE:
                t = base + ","
            else:
                t = base

        # strip other trailing punctuation ; : . ) ] } ! ?
        # Note: drop periods unless covered by the org suffix special-case above
        while t and t[-1] in TRAIL_STRIP or (t and t[-1] == "."):
            if t[-1] in SENTENCE_ENDERS:
                ended_sentence = True
            t = t[:-1]

        # Also strip leading brackets again if any remain after trimming (rare but safe)
        while t and t[0] in LEAD_STRIP:
            t = t[1:]

        return t, ended_sentence

    def tag_token(token: str, is_sentence_start: bool) -> str:
        # 2) Pattern rules (if any left)
        # Currency pair pattern
        if len(token) == 7 and token[3] == "/" and all(is_upper_alpha(c) for c in token[:3]+token[4:7]):
            return "ENTITY"

        # 3) Word lexicons (exact matches)
        # Discourse markers (OTHER), case-insensitive; strip a single trailing comma for matching
        base = token[:-1] if token.endswith(",") else token
        if base.lower() in DISCOURSE_MARKERS_LOWER:
            return "OTHER"

        if token in PREP:
            return "PREP"
        if token in DET:
            return "DET"
        if token in ADJ:
            return "ADJ"
        if token in VERB:
            return "VERB"
        if token in NOUN:
            return "NOUN"
        if token in TIME:
            return "TIME"
        if token in ENTITY_SINGLE:
            return "ENTITY"

        # 4) Heuristics
        # Capitalized mixed-case single Latin word, not sentence-initial
        if not is_sentence_start:
            if token and is_upper_alpha(token[0]) and all(is_alpha(ch) for ch in token):
                # must have at least one lowercase to avoid ALLCAPS
                if any(is_lower_alpha(ch) for ch in token[1:]):
                    return "ENTITY"

        # 5) Fallback
        return "OTHER"

    while i < n:
        i = skip_spaces(i)
        if i >= n:
            break

        # 1) Multi-token merges: company name, currency value, percentage, currency pair
        merged: Optional[Tuple[str, str, int]] = None

        m = match_company_merge(i)
        if m is None:
            m = match_currency_value(i)
        if m is None:
            m = match_percentage(i)
        if m is None:
            m = match_currency_pair(i)
        if m is not None:
            token_text, tag, new_i = m
            out.append([token_text, tag])
            sentence_start = False  # punctuation handling (if any) comes next iterations
            i = new_i
            continue

        # 2) Extract next token per whitespace
        raw_token, next_i = next_raw_token(i)

        # 3) Strip/preserve punctuation per rules
        clean, ended_sent = strip_and_preserve_punct(raw_token)

        # If token becomes empty (punctuation-only), drop it but maintain sentence boundary status
        if not clean:
            if ended_sent:
                sentence_start = True
            i = next_i
            continue

        # 4) Assign tag using precedence: patterns > lexicons (incl. discourse marker) > heuristics > OTHER
        tag = tag_token(clean, sentence_start)

        out.append([clean, tag])

        # Update sentence-start for next token
        if ended_sent:
            sentence_start = True
        else:
            sentence_start = False

        # 6) Advance
        i = next_i

    return out