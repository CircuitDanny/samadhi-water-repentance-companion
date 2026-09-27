# Vietnamese scroll companion translation checkpoint

## Scope and status

Completed Vietnamese commentary translations of:

- `PRACTICE_COMPANION.md`
- `SCROLL_TWO_COMPANION.md`
- `SCROLL_THREE_COMPANION.md`

The translated files are in `translations/vi/` with matching filenames. No English source file was edited as part of this translation work.

These are translations of the companion commentary. They do not claim to be Vietnamese liturgical texts, authorised chant translations or translations reviewed by a monastic.

## Translation approach

- Used natural, respectful Vietnamese suitable for Southern Vietnamese readers without artificial dialect spelling.
- Used established Vietnamese Buddhist forms where the source supported them, including Đức Phật Thích Ca Mâu Ni, Đức Phật A Di Đà, Đức Phật Dược Sư, Bồ-tát Quán Thế Âm, Bồ-tát Văn Thù, Bồ-tát Phổ Hiền, Đức Phật Di Lặc, Tam bảo, Tam-muội, Tịnh độ, Cực Lạc, Bát chánh đạo, ba-la-mật and đà-la-ni.
- Preserved uncertainty and reading cautions from the English commentary rather than resolving disputed lists or transmitted formulae more confidently than the source.
- Preserved Sanskrit and mantra formulae, Latin-letter pronunciation cues, URLs, image paths and source-page numbers exactly.
- Retained quoted English wording where the commentary specifically discusses an English source phrase or typographical error.

## Structural validation

Validated each English and Vietnamese pair line by line and through `markdown-it-py`:

| File | Source lines | Vietnamese lines | Markdown tokens | Block structure | URLs, images, formulae, cues and page references |
|---|---:|---:|---:|---|---|
| `PRACTICE_COMPANION.md` | 586 | 586 | 1,284 each | Exact match | Exact match |
| `SCROLL_TWO_COMPANION.md` | 429 | 429 | 1,085 each | Exact match | Exact match |
| `SCROLL_THREE_COMPANION.md` | 481 | 481 | 1,120 each | Exact match | Exact match |

The structural check compared blank lines, heading levels, table rows and cell counts, bullets, numbered items, blockquotes, hard line breaks and image blocks. All three pairs passed with zero mismatches.

## Terms that may merit specialist review

- **Kanaka** is rendered **Ca-nặc-ca**, a conventional Vietnamese phonetic form. A lineage-specific preferred form may differ.
- **Universal Offering Bodhisattvas** is rendered **các vị Phổ Cúng Dường Bồ-tát** because the English source presents an invoked assembly rather than identifying individual names.
- **Four fruitions and four progressions** is rendered **bốn quả và bốn hướng**, with the explanation retained. A specialist edition may prefer the compact form **tứ hướng tứ quả**.
- **Remorse and shame** is rendered contextually as **hổ thẹn** in the seven-minds table and as **tàm và quý** where the source explicitly distinguishes two protective qualities.
- **Beautiful-Form Tathāgata** is rendered **Đức Diệu Sắc Thân Như Lai**, following common Vietnamese liturgical terminology.
- The inherited English pronunciation cue for “Nam Mô A Di Đà Phật” remains in the translated commentary because the source explains that cue. It is presented as a rough cue, not as Vietnamese liturgical authority.

## Coverage note

Every source heading, paragraph, list item, table cell and quoted explanatory block has a corresponding Vietnamese block. No explanatory material was abridged or omitted.
